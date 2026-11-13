"""Command-line preparation and sequential benchmark matrices."""

import fcntl
import hashlib
import json
import math
import re
import tempfile
import traceback
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from pathlib import Path

import click
from bondi.deployment import get_deployment
from rich.console import Console
from rich.table import Table

from json_bench.experiment import prepare_databases, run_benchmark

console = Console()


def _read(path):
    return json.loads(path.read_text())


def _save(path, value):
    """Replace state atomically, so interruption cannot leave partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def _assets():
    """Read packaged inputs, or the same canonical files in an editable checkout."""
    packaged = Path(__file__).with_name("assets")
    source = packaged if packaged.is_dir() else Path(__file__).resolve().parents[2] / "experiments"
    return {
        "indexes": _read(source / "indexes.json"),
        "templates": [_read(source / "templates" / f"q{i}.json") for i in range(1, 9)],
    }


def _values(text, convert, label, *, zero=False):
    try:
        values = [convert(part.strip()) for part in text.split(",")]
        if not values or any(
            not math.isfinite(v) or v < 0 or (v == 0 and not zero) for v in values
        ):
            raise ValueError
        if len(values) != len(set(values)):
            raise ValueError
        return values
    except (ValueError, TypeError):
        raise click.BadParameter(f"{label} requires distinct, finite positive values.") from None


def _scale_key(value):
    """Keep all significant digits, so distinct scales cannot share a folder."""
    return str(int(value)) if value.is_integer() else str(value)


def _root(experiment, results_dir):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", experiment):
        raise click.BadParameter(
            "Experiment names require 1–64 letters, digits, underscores or hyphens."
        )
    return results_dir.resolve() / experiment


@contextmanager
def _lock(name):
    """Reject overlapping CLI operations; the OS releases locks after a crash."""
    with (Path(tempfile.gettempdir()) / name).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise click.ClickException(
                "Another operation is running. Wait for it to finish."
            ) from None
        yield


def _progress(message):
    console.print(message, markup=False, highlight=False)


def _plan(rows, title):
    console.print(title, markup=False, highlight=False)
    table = Table(expand=True)
    table.add_column("Combination")
    table.add_column("Status")
    for key, status in rows:
        table.add_row(key, status)
    console.print(table)


def _execute(root, state, section, jobs, resume, operation):
    """Keep completed cells and preserve every interrupted or failed attempt."""
    cells = state.setdefault(section, {})
    existing = [key for key in jobs if key in cells]
    if existing and not resume:
        raise click.ClickException("These combinations already exist. Use --resume to continue.")
    for number, (key, params) in enumerate(jobs.items(), 1):
        cell = cells.setdefault(key, {"status": "pending", "attempts": []})
        if cell["status"] == "completed":
            continue
        for previous in cell["attempts"]:
            if previous["status"] == "running":
                previous["status"] = "interrupted"
        attempt = len(cell["attempts"]) + 1
        directory = root / section / key / f"attempt-{attempt}"
        record = {"path": str(directory.relative_to(root)), "status": "running"}
        cell["attempts"].append(record)
        cell["status"] = "running"
        _save(root / "state.json", state)
        directory.mkdir(parents=True)
        _save(directory / "params.json", params)
        console.rule(f"{number}/{len(jobs)} · {key}")
        try:
            operation(key, params, directory)
        except BaseException as error:
            (directory / "error.txt").write_text(traceback.format_exc())
            record.update(status="failed", error_type=type(error).__name__)
            cell["status"] = "failed"
            _save(root / "state.json", state)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise click.ClickException(
                f"{key} failed ({type(error).__name__}). Evidence: {directory}. "
                "Use the same command with --resume after resolving the cause."
            ) from error
        record["status"] = cell["status"] = "completed"
        _save(root / "state.json", state)
    console.print("[green]All selected combinations completed.[/green]")


def _state(root):
    state = _read(root / "state.json")
    if state.get("schema_version") != 1:
        raise click.ClickException("Unsupported experiment state version.")
    return state


def common(function):
    for decorator in reversed(
        [
            click.option("--experiment", required=True, help="Name chosen for this experiment."),
            click.option(
                "--results-dir",
                type=click.Path(path_type=Path),
                default="results",
                show_default=True,
            ),
            click.option(
                "--dry-run",
                is_flag=True,
                help="Show the plan without writing files or starting databases.",
            ),
            click.option(
                "--resume",
                is_flag=True,
                help="Skip completed combinations and retry unfinished ones.",
            ),
        ]
    ):
        function = decorator(function)
    return function


@click.group()
def main():
    """Prepare travel data and run reproducible database benchmark matrices."""


@main.command()
@common
@click.option(
    "--scale-factor", default="0.1", show_default=True, help="Comma-separated scale factors."
)
@click.option("--seed", type=int, default=23, show_default=True)
@click.option("--reference-date", default="2025-11-01", show_default=True)
@click.option("--mongodb-version", default="8.2.1", show_default=True)
@click.option("--couchbase-version", default="8.0.0", show_default=True)
@click.option("--memory-limit-mb", type=click.IntRange(min=1), default=24576, show_default=True)
@click.option(
    "--mongodb-cache-gb", type=click.FloatRange(min=0, min_open=True), default=12, show_default=True
)
@click.option("--couchbase-data-mb", type=click.IntRange(min=1), default=8192, show_default=True)
@click.option("--couchbase-index-mb", type=click.IntRange(min=1), default=4096, show_default=True)
@click.option("--mongodb-port", type=click.IntRange(1, 65535), default=27147, show_default=True)
@click.option(
    "--couchbase-management-port", type=click.IntRange(1, 65535), default=18491, show_default=True
)
@click.option(
    "--couchbase-query-port", type=click.IntRange(1, 65535), default=18493, show_default=True
)
@click.option(
    "--couchbase-kv-port", type=click.IntRange(1, 65535), default=21430, show_default=True
)
def prepare(
    experiment,
    results_dir,
    dry_run,
    resume,
    scale_factor,
    seed,
    reference_date,
    mongodb_version,
    couchbase_version,
    memory_limit_mb,
    mongodb_cache_gb,
    couchbase_data_mb,
    couchbase_index_mb,
    mongodb_port,
    couchbase_management_port,
    couchbase_query_port,
    couchbase_kv_port,
):
    """Create a stopped MongoDB/Couchbase pair for each scale factor."""
    scales = sorted(_values(scale_factor, float, "Scale factors"))
    if any(sf < 0.01 for sf in scales):
        raise click.BadParameter("Scale factors must be at least 0.01.")
    try:
        date.fromisoformat(reference_date)
    except ValueError:
        raise click.BadParameter("Use YYYY-MM-DD for --reference-date.") from None
    ports = [mongodb_port, couchbase_management_port, couchbase_query_port, couchbase_kv_port]
    if len(set(ports)) != len(ports):
        raise click.BadParameter("Database ports must be distinct.")
    if not math.isfinite(mongodb_cache_gb) or mongodb_cache_gb * 1024 >= memory_limit_mb:
        raise click.BadParameter("MongoDB cache must be smaller than the total memory limit.")
    if couchbase_data_mb + couchbase_index_mb >= memory_limit_mb:
        raise click.BadParameter("Couchbase quotas must sum to less than the total memory limit.")
    params = dict(
        seed=seed,
        reference_date=reference_date,
        mongodb=dict(
            version=mongodb_version,
            port=mongodb_port,
            memory_limit_mb=memory_limit_mb,
            wiredtiger_cache_size_gb=mongodb_cache_gb,
        ),
        couchbase=dict(
            version=couchbase_version,
            memory_limit_mb=memory_limit_mb,
            data_mb=couchbase_data_mb,
            index_mb=couchbase_index_mb,
            management_port=couchbase_management_port,
            query_port=couchbase_query_port,
            kv_port=couchbase_kv_port,
        ),
    )
    jobs = {f"sf-{_scale_key(sf)}": dict(params, scale_factor=sf) for sf in scales}
    root = _root(experiment, results_dir)
    plan = {"jobs": jobs, "assets": _assets()}
    with _lock("json-bench-cli.lock"):
        if (root / "state.json").exists():
            state = _state(root)
            if state["preparation_plan"] != plan:
                raise click.ClickException(
                    "Preparation settings changed. Choose a new experiment name."
                )
            if not resume:
                raise click.ClickException("Experiment already exists. Use --resume or a new name.")
        else:
            if root.exists() and any(root.iterdir()):
                raise click.ClickException(
                    "Output folder is not empty. Choose a new experiment name."
                )
            state = {"schema_version": 1, "preparation_plan": plan, "preparations": {}, "runs": {}}
        _plan(
            [(key, state["preparations"].get(key, {}).get("status", "pending")) for key in jobs],
            f"Prepare {len(jobs)} dataset pairs · {root}",
        )
        if dry_run:
            return
        # Share the benchmark lock during preparation, but not around run_benchmark,
        # which takes that lock itself. This also excludes active Yanex benchmarks.
        with _lock("bondi-json-bench-benchmark.lock"):

            def operation(key, config, directory):
                suffix = hashlib.sha256(f"{root}/{key}".encode()).hexdigest()[:16]
                if len(state["preparations"][key]["attempts"]) > 1:
                    # A killed preparation process may leave either backend running.
                    for backend in ("mongodb", "couchbase"):
                        try:
                            deployment = get_deployment(f"jsonbench-{backend}-cli-{suffix}")
                        except FileNotFoundError:
                            continue
                        deployment.stop()
                prepare_databases(
                    config,
                    run_id=f"cli-{suffix}",
                    indexes=plan["assets"]["indexes"],
                    output_dir=directory,
                    on_progress=_progress,
                )

            _execute(root, state, "preparations", jobs, resume, operation)


@main.command()
@common
@click.option(
    "--scale-factor", default=None, help="Comma-separated subset; defaults to all prepared scales."
)
@click.option("--backend", default="mongodb,couchbase", show_default=True)
@click.option("--clients", default="2", show_default=True, help="Comma-separated client counts.")
@click.option("--repetitions", type=click.IntRange(min=1), default=1, show_default=True)
@click.option("--seed", type=int, default=23, show_default=True)
@click.option("--warmup-seconds", type=click.FloatRange(min=0), default=60, show_default=True)
@click.option(
    "--measurement-seconds",
    type=click.FloatRange(min=0, min_open=True),
    default=180,
    show_default=True,
)
@click.option(
    "--drain-timeout-seconds", type=click.FloatRange(min=0), default=60, show_default=True
)
@click.option(
    "--timeout-seconds", type=click.FloatRange(min=0, min_open=True), default=60, show_default=True
)
@click.option(
    "--health-check-timeout-seconds",
    type=click.FloatRange(min=0, min_open=True),
    default=60,
    show_default=True,
)
@click.option(
    "--startup-timeout-seconds",
    type=click.FloatRange(min=0, min_open=True),
    default=300,
    show_default=True,
)
@click.option(
    "--weights", default="1,1,1,1,1,1,1,1", show_default=True, help="Q1–Q8 selection weights."
)
@click.option("--q4-location", default="Donnafurt", show_default=True)
def benchmark(
    experiment,
    results_dir,
    dry_run,
    resume,
    scale_factor,
    backend,
    clients,
    repetitions,
    seed,
    warmup_seconds,
    measurement_seconds,
    drain_timeout_seconds,
    timeout_seconds,
    health_check_timeout_seconds,
    startup_timeout_seconds,
    weights,
    q4_location,
):
    """Run combinations sequentially against prepared databases."""
    root = _root(experiment, results_dir)
    if not (root / "state.json").exists():
        raise click.ClickException("Experiment is not prepared. Run json-bench prepare first.")
    backends = [part.strip() for part in backend.split(",")]
    if len(set(backends)) != len(backends) or not set(backends) <= {"mongodb", "couchbase"}:
        raise click.BadParameter("--backend must list mongodb, couchbase, or both.")
    counts = sorted(_values(clients, int, "Client counts"))
    try:
        weights = [float(part) for part in weights.split(",")]
        if (
            len(weights) != 8
            or any(not math.isfinite(w) or w < 0 for w in weights)
            or not sum(weights)
        ):
            raise ValueError
    except ValueError:
        raise click.BadParameter(
            "Supply eight finite nonnegative weights, with at least one positive weight."
        ) from None
    timings = [
        warmup_seconds,
        measurement_seconds,
        drain_timeout_seconds,
        timeout_seconds,
        health_check_timeout_seconds,
        startup_timeout_seconds,
    ]
    if not all(math.isfinite(value) for value in timings):
        raise click.BadParameter("Durations must be finite.")
    with _lock("json-bench-cli.lock"):
        state = _state(root)
        prepared = state["preparation_plan"]["jobs"]
        scales = (
            sorted(_values(scale_factor, float, "Scale factors"))
            if scale_factor
            else [p["scale_factor"] for p in prepared.values()]
        )
        for sf in scales:
            if state["preparations"].get(f"sf-{_scale_key(sf)}", {}).get("status") != "completed":
                raise click.ClickException(
                    f"Scale factor {_scale_key(sf)} is not prepared. Finish preparation first."
                )
        jobs = {}
        for db in backends:
            for sf in scales:
                for repetition in range(1, repetitions + 1):
                    for count in counts:
                        key = f"{db}-sf-{_scale_key(sf)}-clients-{count}-rep-{repetition}"
                        jobs[key] = dict(
                            backend=db,
                            scale_factor=sf,
                            repetition=repetition,
                            clients=count,
                            seed=seed + repetition - 1,
                            load=dict(
                                warmup_seconds=warmup_seconds,
                                measurement_seconds=measurement_seconds,
                                drain_timeout_seconds=drain_timeout_seconds,
                                weights=weights,
                            ),
                            executor=dict(
                                timeout_seconds=timeout_seconds,
                                health_check_timeout_seconds=health_check_timeout_seconds,
                            ),
                            deployment=dict(startup_timeout_seconds=startup_timeout_seconds),
                            queries=dict(q4_location=q4_location),
                        )
        settings = deepcopy(next(iter(jobs.values())))
        for dimension in ("backend", "scale_factor", "repetition", "clients"):
            settings.pop(dimension)
        settings["seed"] = seed
        if state.get("benchmark_settings", settings) != settings:
            raise click.ClickException(
                "Benchmark settings changed. Resume with the original options or use a new experiment."
            )
        if state["runs"] and not resume:
            raise click.ClickException("Benchmark runs already exist. Use --resume to continue.")
        _plan(
            [(key, state["runs"].get(key, {}).get("status", "pending")) for key in jobs],
            f"Benchmark {len(jobs)} combinations · {root}",
        )
        if dry_run:
            return
        state["benchmark_settings"] = settings
        state.setdefault("benchmark_plan", {}).update(jobs)

        def operation(key, config, directory):
            config = deepcopy(config)
            sf = config.pop("scale_factor")
            config.pop("repetition")
            cell = state["preparations"][f"sf-{_scale_key(sf)}"]
            manifest = _read(root / cell["attempts"][-1]["path"] / "preparation.json")
            run_benchmark(
                manifest,
                config,
                scale_factor=sf,
                templates=state["preparation_plan"]["assets"]["templates"],
                output_dir=directory,
                on_progress=_progress,
            )

        _execute(root, state, "runs", jobs, resume, operation)
