"""Shared experiment contracts without databases or an experiment tracker."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from bondi.execution import ExecutionResult
from bondi.load import LoadResult

from json_bench import experiment as exp
from json_bench.queries import load_template

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(exp.tempfile, "gettempdir", lambda: str(tmp_path))
    events = []
    deployments = {}
    for backend in ("mongodb", "couchbase"):
        db = SimpleNamespace(
            backend=backend,
            name=f"jsonbench-{backend}-example",
            uri=f"{backend}://local",
            image=backend,
            username="admin",
            password="test",
            stop=MagicMock(side_effect=lambda b=backend: events.append(("stop", b))),
            start=MagicMock(side_effect=lambda **kw: events.append(("start", kw))),
        )
        deployments[backend] = db

        def deploy(name, b=backend, **kwargs):
            events.append(("deploy", b, kwargs))
            return deployments[b]

        monkeypatch.setattr(exp, f"deploy_{backend}", deploy)
    monkeypatch.setattr(
        exp,
        "get_deployment",
        lambda name: next(db for db in deployments.values() if db.name == name),
    )
    monkeypatch.setattr(exp, "create_indexes", MagicMock(return_value={}))
    return deployments, events


def params(name):
    return yaml.safe_load((ROOT / "experiments/configs" / f"{name}.yaml").read_text())


def test_preparation_retains_protocol_and_artifacts(tmp_path, monkeypatch, setup):
    deployments, events = setup
    data = {"users": [{"_id": "u1"}], "tours": [], "bookings": [], "reviews": []}
    generator = MagicMock(return_value=data)
    monkeypatch.setattr(exp, "generate_travel_dataset", generator)
    loader = MagicMock(
        side_effect=lambda docs, **kwargs: SimpleNamespace(
            uncertain_writes=False, destinations={"collection": len(docs)}
        )
    )
    monkeypatch.setattr(exp, "load_documents", loader)
    metrics = []
    config = params("prepare")
    indexes = {
        "mongodb": {"bookings": [{"fields": ["tour_id"], "name": "baseline"}]},
        "couchbase": {},
    }
    manifest = exp.prepare_databases(
        config,
        run_id="example",
        indexes=indexes,
        output_dir=tmp_path,
        on_progress=lambda _: None,
        on_metrics=metrics.append,
    )
    assert manifest == json.loads((tmp_path / "preparation.json").read_text())
    from bondi import IndexSet

    for backend in indexes:
        restored = IndexSet.load(tmp_path / f"indexes.{backend}.json")
        assert restored.to_dict() == IndexSet.from_dict(indexes[backend]).to_dict()
        assert json.loads((tmp_path / f"index_names.{backend}.json").read_text()) == {}
    assert manifest["status"] == "ready"
    assert metrics == [{"documents_per_backend": 1}]
    generator.assert_called_once_with(
        scale=config["scale_factor"], seed=config["seed"], reference_date=config["reference_date"]
    )
    assert [e[:2] for e in events] == [
        ("deploy", "mongodb"),
        ("stop", "mongodb"),
        ("deploy", "couchbase"),
        ("stop", "couchbase"),
    ]
    assert loader.call_count == 8
    assert all(call.kwargs["mode"] == "replace" for call in loader.call_args_list)
    assert events[0][2]["wiredtiger_cache_size_gb"] == 12
    assert events[2][2]["memory_limit_mb"] == 24576
    assert events[2][2]["data_memory_mb"] == config["couchbase"]["data_mb"]
    assert events[2][2]["index_memory_mb"] == config["couchbase"]["index_mb"]
    assert json.loads((tmp_path / "indexes.json").read_text()) == indexes


def test_incomplete_load_saves_failure_and_stops(tmp_path, monkeypatch, setup):
    deployments, events = setup
    monkeypatch.setattr(exp, "generate_travel_dataset", lambda **_: {"users": [{}]})
    monkeypatch.setattr(
        exp,
        "load_documents",
        lambda *a, **kw: SimpleNamespace(uncertain_writes=True, destinations={}),
    )
    with pytest.raises(RuntimeError, match="Incomplete load"):
        exp.prepare_databases(
            params("prepare"),
            run_id="example",
            indexes={"mongodb": {}, "couchbase": {}},
            output_dir=tmp_path,
            on_progress=lambda _: None,
        )
    assert json.loads((tmp_path / "preparation.json").read_text())["status"] == "failed"
    deployments["mongodb"].stop.assert_called_once()
    assert not any(e[:2] == ("deploy", "couchbase") for e in events)


@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
@pytest.mark.parametrize("early_stop", [False, True])
def test_benchmark_preserves_results_and_cleanup(tmp_path, monkeypatch, setup, backend, early_stop):
    deployments, events = setup
    config = params("benchmark")
    config["backend"] = backend
    manifest = {
        "schema_version": 1,
        "status": "ready",
        "experiment_id": "example",
        "database": "travel",
        "scope": "_default",
        "deployments": {b: {"name": d.name} for b, d in deployments.items()},
    }
    templates = [load_template(ROOT / "experiments/templates" / f"q{i}.json") for i in range(1, 9)]
    original = deepcopy(templates)
    warmup = config["load"]["warmup_seconds"]
    results = [
        LoadResult(
            0,
            0,
            0,
            0,
            "measurement",
            warmup + 1,
            warmup + 2,
            True,
            ExecutionResult(1000, error=RuntimeError() if early_stop else None),
            stop_reason="database_unavailable" if early_stop else None,
        )
    ]
    executor = MagicMock()
    executor.__enter__.return_value = executor

    def generate(workload, **kwargs):
        assert len(workload) == 8
        assert kwargs["collect_results"] is False
        assert kwargs["return_load_results"] is True
        assert kwargs["warmup_seconds"] == warmup
        assert kwargs["measurement_seconds"] == config["load"]["measurement_seconds"]
        for result in results:
            kwargs["on_result"](result)
        return results

    executor.generate_load.side_effect = generate
    factory = MagicMock(return_value=executor)
    monkeypatch.setattr(
        getattr(exp, "MongoExecutor" if backend == "mongodb" else "CouchbaseExecutor"),
        "from_uri",
        factory,
    )
    metrics, streamed, artifacts = [], [], {}

    def save(value, name):
        artifacts[name] = deepcopy(value)
        (tmp_path / name).write_text(json.dumps(value))

    def run():
        return exp.run_benchmark(
            manifest,
            config,
            scale_factor=10,
            templates=templates,
            output_dir=tmp_path,
            on_artifact=save,
            on_metrics=metrics.append,
            on_result=streamed.append,
            on_progress=lambda _: None,
        )

    if early_stop:
        with pytest.raises(RuntimeError, match="stopped early"):
            run()
    else:
        analysis = run()
        assert analysis.summary.success_count == 1
    assert templates == original
    assert streamed == results
    assert len(metrics) == 1
    assert artifacts["summary.json"]["early_terminated"] == early_stop
    assert len(artifacts["per_query.json"]) == 8
    assert artifacts["benchmark.json"]["scale_factor"] == 10
    assert set(artifacts) == {
        "templates.json",
        "queries.json",
        "benchmark.json",
        "summary.json",
        "per_query.json",
    }
    record = json.loads((tmp_path / "load_results.jsonl").read_text())
    assert record["result"]["status"] == ("error" if early_stop else "success")
    assert factory.call_args.kwargs["continue_on_error"] is True
    assert factory.call_args.kwargs["concurrency"] == config["clients"]
    assert events[:2] == [("stop", "mongodb"), ("stop", "couchbase")]
    assert events[-1] == ("stop", backend)
    deployments[backend].start.assert_called_once_with(
        timeout=config["deployment"]["startup_timeout_seconds"]
    )


def test_failed_startup_stops_saved_deployment(tmp_path, monkeypatch, setup):
    deployments, _ = setup
    monkeypatch.setattr(exp, "generate_travel_dataset", lambda **_: {"users": []})

    def failed_start(*args, **kwargs):
        raise RuntimeError("startup failed after registration")

    monkeypatch.setattr(exp, "deploy_mongodb", failed_start)
    with pytest.raises(RuntimeError, match="startup failed"):
        exp.prepare_databases(
            params("prepare"),
            run_id="example",
            indexes={"mongodb": {}, "couchbase": {}},
            output_dir=tmp_path,
            on_progress=lambda _: None,
        )
    deployments["mongodb"].stop.assert_called_once()
    assert json.loads((tmp_path / "preparation.json").read_text())["error_type"] == "RuntimeError"


def test_load_dataset_rejects_short_acknowledged_count(monkeypatch, setup):
    deployments, _ = setup
    monkeypatch.setattr(
        exp,
        "load_documents",
        lambda *a, **kw: SimpleNamespace(uncertain_writes=False, destinations={"users": 0}),
    )
    with pytest.raises(RuntimeError, match="Incomplete load"):
        exp.load_dataset(deployments["mongodb"], {"users": [{}]}, on_progress=lambda _: None)


def test_progress_callback_cannot_prevent_shutdown(tmp_path, monkeypatch, setup):
    deployments, _ = setup
    monkeypatch.setattr(exp, "generate_travel_dataset", lambda **_: {})

    def progress(message):
        if "Stopping" in message:
            raise RuntimeError("reporter failed")

    with pytest.raises(RuntimeError, match="reporter failed"):
        exp.prepare_databases(
            params("prepare"),
            run_id="example",
            indexes={"mongodb": {}, "couchbase": {}},
            output_dir=tmp_path,
            on_progress=progress,
        )
    deployments["mongodb"].stop.assert_called_once()


def test_old_index_configuration_rejected_before_generation(tmp_path, monkeypatch):
    generator = MagicMock()
    monkeypatch.setattr(exp, "generate_travel_dataset", generator)
    with pytest.raises((ValueError, TypeError)):
        exp.prepare_databases(
            params("prepare"),
            run_id="old",
            output_dir=tmp_path,
            indexes={"mongodb": {"bookings": ["tour_id"]}, "couchbase": {}},
        )
    generator.assert_not_called()
