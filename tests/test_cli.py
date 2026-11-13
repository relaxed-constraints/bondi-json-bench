"""Exercise matrix planning and recovery without starting databases."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from json_bench import cli


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: str(tmp_path))
    calls = []

    def missing_deployment(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr(cli, "get_deployment", missing_deployment)

    def prepare(params, **kwargs):
        calls.append(("prepare", params, kwargs))
        cli._save(
            kwargs["output_dir"] / "preparation.json",
            {
                "schema_version": 1,
                "status": "ready",
                "experiment_id": kwargs["run_id"],
            },
        )

    def benchmark(manifest, params, **kwargs):
        calls.append(("benchmark", params, kwargs))
        cli._save(kwargs["output_dir"] / "summary.json", {"error_count": 2})

    monkeypatch.setattr(cli, "prepare_databases", prepare)
    monkeypatch.setattr(cli, "run_benchmark", benchmark)
    runner = CliRunner()

    def invoke(command, *args):
        return runner.invoke(
            cli.main,
            [command, "--experiment", "test", "--results-dir", str(tmp_path / "results"), *args],
        )

    return invoke, calls, tmp_path / "results/test"


def test_full_matrix_and_resume(app):
    invoke, calls, root = app
    assert invoke("prepare", "--scale-factor", "10,100,200").exit_code == 0
    assert len(calls) == 3
    args = ("--clients", "2,4,8,16,32,64", "--repetitions", "3")
    preview = invoke("benchmark", *args, "--dry-run")
    assert preview.exit_code == 0, preview.output
    assert "108 combinations" in preview.output
    assert len(calls) == 3
    result = invoke("benchmark", *args)
    assert result.exit_code == 0, result.output
    assert len(calls) == 111
    benchmarks = calls[3:]
    assert [c[1]["backend"] for c in benchmarks[:54]] == ["mongodb"] * 54
    assert {c[1]["seed"] for c in benchmarks} == {23, 24, 25}
    assert invoke("benchmark", *args, "--resume").exit_code == 0
    assert len(calls) == 111  # Successful runs with query errors are still complete.
    assert invoke("benchmark", *args).exit_code != 0
    assert invoke("benchmark", *args, "--resume", "--timeout-seconds", "30").exit_code != 0
    state = cli._read(root / "state.json")
    assert len(state["runs"]) == 108
    assert all(cell["status"] == "completed" for cell in state["runs"].values())


def test_preparation_dry_run_and_input_validation(app):
    invoke, calls, root = app
    assert invoke("prepare", "--scale-factor", "10,100,200", "--dry-run").exit_code == 0
    assert not root.exists()
    assert not calls
    for value in ("nan", "inf", "0", "-1", "1,1", "0.001", "bad", "1,"):
        assert invoke("prepare", "--scale-factor", value).exit_code != 0
    assert invoke("prepare", "--reference-date", "tomorrow").exit_code != 0
    assert invoke("prepare", "--memory-limit-mb", "100").exit_code != 0
    assert invoke("prepare", "--mongodb-port", "18491").exit_code != 0
    assert invoke("prepare", "--experiment", "../escape").exit_code != 0
    assert not calls


def test_preparation_resume_and_exact_scales(app):
    invoke, calls, root = app
    args = ("--scale-factor", "1.000001,1.000002")
    assert invoke("prepare", *args).exit_code == 0
    assert len(cli._read(root / "state.json")["preparations"]) == 2
    assert invoke("prepare", *args, "--resume").exit_code == 0
    assert len(calls) == 2
    assert invoke("prepare", *args).exit_code != 0
    assert invoke("prepare", *args, "--resume", "--seed", "99").exit_code != 0


def test_failed_benchmark_preserves_attempt_and_resumes(app, monkeypatch):
    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    real = cli.run_benchmark

    def fail(*args, **kwargs):
        (kwargs["output_dir"] / "load_results.jsonl").write_text("partial evidence\n")
        raise RuntimeError("probe failure")

    monkeypatch.setattr(cli, "run_benchmark", fail)
    assert invoke("benchmark", "--backend", "mongodb").exit_code != 0
    state = cli._read(root / "state.json")
    cell = next(iter(state["runs"].values()))
    old_path = root / cell["attempts"][0]["path"]
    assert cell["status"] == "failed"
    monkeypatch.setattr(cli, "run_benchmark", real)
    assert invoke("benchmark", "--backend", "mongodb", "--resume").exit_code == 0
    assert (old_path / "load_results.jsonl").read_text() == "partial evidence\n"
    assert "probe failure" in (old_path / "error.txt").read_text()
    cell = next(iter(cli._read(root / "state.json")["runs"].values()))
    assert [a["status"] for a in cell["attempts"]] == ["failed", "completed"]


def test_interrupted_preparation_resume_keeps_completed_scales(app, monkeypatch):
    invoke, calls, root = app
    original = cli.prepare_databases

    def fail(params, **kwargs):
        if params["scale_factor"] == 100:
            raise KeyboardInterrupt
        return original(params, **kwargs)

    monkeypatch.setattr(cli, "prepare_databases", fail)
    assert invoke("prepare", "--scale-factor", "10,100").exit_code != 0
    monkeypatch.setattr(cli, "prepare_databases", original)
    assert invoke("prepare", "--scale-factor", "10,100", "--resume").exit_code == 0
    assert [call[1]["scale_factor"] for call in calls] == [10, 100]
    assert len(cli._read(root / "state.json")["preparations"]["sf-100"]["attempts"]) == 2


def test_stale_running_attempt_is_retained(app):
    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    assert invoke("benchmark", "--backend", "mongodb").exit_code == 0
    state = cli._read(root / "state.json")
    cell = next(iter(state["runs"].values()))
    cell["status"] = cell["attempts"][0]["status"] = "running"
    cli._save(root / "state.json", state)
    assert invoke("benchmark", "--backend", "mongodb", "--resume").exit_code == 0
    cell = next(iter(cli._read(root / "state.json")["runs"].values()))
    assert len(cell["attempts"]) == 2


def test_selection_can_expand_without_repeating_cells(app):
    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    assert invoke("benchmark", "--backend", "mongodb").exit_code == 0
    assert invoke("benchmark", "--clients", "2,4", "--resume").exit_code == 0
    assert len(calls) == 5  # one preparation, four distinct runs


def test_preconditions_and_weights(app):
    invoke, calls, root = app
    assert invoke("benchmark").exit_code != 0
    assert invoke("prepare").exit_code == 0
    for args in [
        ("--backend", "unknown"),
        ("--clients", "0"),
        ("--clients", "2,2"),
        ("--scale-factor", "200"),
        ("--weights", "0,0,0,0,0,0,0,0"),
        ("--weights", "nan,1,1,1,1,1,1,1"),
        ("--measurement-seconds", "nan"),
    ]:
        assert invoke("benchmark", *args).exit_code != 0
    assert invoke("benchmark", "--weights", "3,1,0,0,0,0,0,0").exit_code == 0
    assert calls[-1][1]["load"]["weights"] == [3, 1, 0, 0, 0, 0, 0, 0]


def test_lock_prevents_writes(app):
    invoke, calls, root = app
    with cli._lock("json-bench-cli.lock"):
        result = invoke("prepare")
    assert result.exit_code != 0
    assert not calls
    assert not root.exists()


def test_assets_match_canonical_inputs():
    source = Path(__file__).resolve().parents[1] / "experiments"
    assets = cli._assets()
    assert assets["indexes"] == json.loads((source / "indexes.json").read_text())
    assert len(assets["templates"]) == 8
    for i, template in enumerate(assets["templates"], 1):
        assert template == json.loads((source / "templates" / f"q{i}.json").read_text())


def test_preparation_retry_stops_both_owned_databases(app, monkeypatch):
    from types import SimpleNamespace

    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    state = cli._read(root / "state.json")
    state["preparations"]["sf-0.1"]["status"] = "running"
    cli._save(root / "state.json", state)
    stopped = []
    monkeypatch.setattr(
        cli, "get_deployment", lambda name: SimpleNamespace(stop=lambda: stopped.append(name))
    )
    assert invoke("prepare", "--resume").exit_code == 0
    assert len(stopped) == 2
    assert stopped[0] == "jsonbench-mongodb-test-sf-0-1"
    assert stopped[1] == "jsonbench-couchbase-test-sf-0-1"


def cleanup_fixture(app, monkeypatch):
    from types import SimpleNamespace

    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    state = cli._read(root / "state.json")
    path = root / state["preparations"]["sf-0.1"]["attempts"][0]["path"] / "preparation.json"
    manifest = cli._read(path)
    manifest["deployments"] = {
        backend: {"name": f"jsonbench-{backend}-cleanup-test"}
        for backend in ("mongodb", "couchbase")
    }
    cli._save(path, manifest)
    removed = []
    monkeypatch.setattr(
        cli, "get_deployment", lambda name: SimpleNamespace(remove=lambda: removed.append(name))
    )
    return invoke, root, path, removed


def test_cleanup_confirmation_and_artifact_preservation(app, monkeypatch):
    invoke, root, path, removed = cleanup_fixture(app, monkeypatch)
    before = path.read_bytes()
    state_before = (root / "state.json").read_bytes()
    assert invoke("cleanup", "--dry-run").exit_code == 0
    assert not removed
    # CliRunner supplies no answer: the default is cancellation.
    assert invoke("cleanup").exit_code != 0
    assert not removed
    assert (root / "state.json").read_bytes() == state_before
    result = CliRunner().invoke(
        cli.main,
        ["cleanup", "--experiment", "test", "--results-dir", str(root.parent)],
        input="y\n",
    )
    assert result.exit_code == 0, result.output
    assert sorted(removed) == ["jsonbench-couchbase-cleanup-test", "jsonbench-mongodb-cleanup-test"]
    assert path.read_bytes() == before
    assert cli._read(root / "state.json")["cleanup"]["status"] == "completed"
    assert invoke("benchmark", "--resume").exit_code != 0
    assert invoke("prepare", "--resume").exit_code != 0


def test_cleanup_partial_failure_and_missing_deployment(app, monkeypatch):
    from types import SimpleNamespace

    invoke, root, path, removed = cleanup_fixture(app, monkeypatch)

    def find(name):
        if "couchbase" in name:
            raise FileNotFoundError(name)

        def fail():
            raise RuntimeError("removal failed")

        return SimpleNamespace(remove=fail)

    monkeypatch.setattr(cli, "get_deployment", find)
    assert invoke("cleanup", "--yes").exit_code != 0
    assert cli._read(root / "state.json")["cleanup"]["status"] == "failed"
    monkeypatch.setattr(
        cli, "get_deployment", lambda name: SimpleNamespace(remove=lambda: removed.append(name))
    )
    assert invoke("cleanup", "--yes").exit_code == 0
    assert path.exists()


def test_cleanup_checks_all_attempts_and_deduplicates(app, monkeypatch):
    invoke, root, path, removed = cleanup_fixture(app, monkeypatch)
    state = cli._read(root / "state.json")
    cell = state["preparations"]["sf-0.1"]
    cell["attempts"].append(dict(cell["attempts"][0]))
    cli._save(root / "state.json", state)
    assert invoke("cleanup", "--yes").exit_code == 0
    assert len(removed) == 2


def test_cleanup_rejects_unrelated_names(app, monkeypatch):
    invoke, root, path, removed = cleanup_fixture(app, monkeypatch)
    manifest = cli._read(path)
    manifest["deployments"]["mongodb"]["name"] = "json-storm-mongo"
    cli._save(path, manifest)
    assert invoke("cleanup", "--yes").exit_code != 0
    assert not removed


def test_readable_names_and_length_validation(app):
    invoke, calls, root = app
    assert invoke("prepare", "--scale-factor", "0.1,0.5").exit_code == 0
    assert [c[2]["run_id"] for c in calls] == ["test-sf-0-1", "test-sf-0-5"]
    assert cli._readable_id("My_Run", 10.0) == "my-run-sf-10"
    with pytest.raises(Exception, match="shorter experiment name"):
        cli._readable_id("x" * 40, 10.0)


def test_new_experiment_rejects_existing_deployments(app, monkeypatch):
    from types import SimpleNamespace

    invoke, calls, root = app
    monkeypatch.setattr(cli, "get_deployment", lambda name: SimpleNamespace(name=name))
    result = invoke("prepare")
    assert result.exit_code != 0
    assert "already exists" in result.output
    assert not calls
    assert not root.exists()


def test_legacy_resume_uses_manifest_identity_and_cleanup(app, monkeypatch):
    from types import SimpleNamespace

    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    state = cli._read(root / "state.json")
    state.pop("deployment_ids")
    cell = state["preparations"]["sf-0.1"]
    cell["status"] = "failed"
    manifest_path = root / cell["attempts"][0]["path"] / "preparation.json"
    legacy = "cli-b6e87af1ecbcd173"
    manifest = cli._read(manifest_path)
    manifest["experiment_id"] = legacy
    manifest["deployments"] = {
        b: {"name": f"jsonbench-{b}-{legacy}"} for b in ("mongodb", "couchbase")
    }
    cli._save(manifest_path, manifest)
    cli._save(root / "state.json", state)
    stopped, removed = [], []
    monkeypatch.setattr(
        cli,
        "get_deployment",
        lambda name: SimpleNamespace(
            stop=lambda: stopped.append(name), remove=lambda: removed.append(name)
        ),
    )
    assert invoke("prepare", "--resume").exit_code == 0
    assert calls[-1][2]["run_id"] == legacy
    assert set(stopped) == {f"jsonbench-{b}-{legacy}" for b in ("mongodb", "couchbase")}
    assert invoke("cleanup", "--yes").exit_code == 0
    assert set(removed) == set(stopped)
    assert manifest_path.exists()


def test_legacy_unstarted_scales_keep_hash_identity(app):
    import hashlib

    invoke, calls, root = app
    assert invoke("prepare", "--scale-factor", "0.1,0.5").exit_code == 0
    state = cli._read(root / "state.json")
    state.pop("deployment_ids")
    state["preparations"].pop("sf-0.5")
    import shutil

    shutil.rmtree(root / "preparations" / "sf-0.5")
    cli._save(root / "state.json", state)
    assert invoke("prepare", "--scale-factor", "0.1,0.5", "--resume").exit_code == 0
    expected = "cli-" + hashlib.sha256(f"{root.resolve()}/sf-0.5".encode()).hexdigest()[:16]
    assert calls[-1][2]["run_id"] == expected


def test_plot_exports_png_pdf_after_cleanup_and_skips_failed_runs(app):
    invoke, calls, root = app
    assert invoke("prepare").exit_code == 0
    assert invoke("benchmark").exit_code == 0
    state = cli._read(root / "state.json")
    counts = dict(success_count=2, error_count=1, timeout_count=0, unresolved_count=0)
    for cell in state["runs"].values():
        directory = root / cell["attempts"][0]["path"]
        cli._save(
            directory / "summary.json",
            dict(
                **counts,
                measurement_admissions=3,
                early_terminated=False,
                throughput_queries_per_second=1,
                mean_runtime_seconds=1.5,
            ),
        )
        cli._save(
            directory / "per_query.json",
            [
                dict(
                    **counts,
                    label="Q1",
                    workload_position=0,
                    successful_runtime_seconds=[1.0, 2.0],
                )
            ],
        )
    state["runs"]["failed-run"] = {"status": "failed", "attempts": []}
    state["cleanup"] = {"status": "completed"}
    cli._save(root / "state.json", state)
    before = (root / "state.json").read_bytes()
    with cli._lock("json-bench-cli.lock"):
        result = invoke("plot")
    assert result.exit_code == 0, result.output
    assert "Skipping 1" in result.output
    assert (root / "state.json").read_bytes() == before
    output = root / "figures"
    assert len(list(output.glob("*.png"))) == 7
    assert len(list(output.glob("*.pdf"))) == 7
    for path in output.glob("*.png"):
        assert path.read_bytes().startswith(b"\x89PNG")
    for path in output.glob("*.pdf"):
        assert path.read_bytes().startswith(b"%PDF")
    report = cli._read(output / "plot_manifest.json")
    assert len(report["included_attempts"]) == 2
    assert report["skipped_runs"] == {"failed-run": "failed"}
    assert report["dpi"] == 200


def test_plot_requires_completed_valid_artifacts(app):
    invoke, calls, root = app
    assert invoke("plot").exit_code != 0
    assert invoke("prepare").exit_code == 0
    result = invoke("plot")
    assert "No completed benchmark runs" in result.output
    assert invoke("benchmark").exit_code == 0
    result = invoke("plot")
    assert result.exit_code != 0
    assert "Cannot read completed run" in result.output
    assert not (root / "figures").exists()
