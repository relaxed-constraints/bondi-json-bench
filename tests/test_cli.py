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
    assert stopped[0].startswith("jsonbench-mongodb-cli-")
    assert stopped[1].startswith("jsonbench-couchbase-cli-")
