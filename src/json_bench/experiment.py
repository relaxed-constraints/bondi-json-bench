"""Shared preparation and benchmark execution, independent of experiment tracking."""

import fcntl
import json
import tempfile
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from bondi.couchbase import CouchbaseCollectionRef, CouchbaseExecutor
from bondi.data import load_documents
from bondi.deployment import deploy_couchbase, deploy_mongodb, get_deployment
from bondi.load import WeightedRandom
from bondi.mongodb import MongoCollectionRef, MongoExecutor
from bondi.workload import Workload, WorkloadEntry
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from pymongo import MongoClient

from json_bench.analysis import analyse_load_results, load_result_record
from json_bench.data import generate_travel_dataset
from json_bench.deployment import configure_couchbase
from json_bench.indexes import ensure_couchbase_indexes, ensure_mongodb_indexes
from json_bench.queries import translate_couchbase, translate_mongodb


def _print_progress(message):
    """Flush progress immediately when no caller-specific reporter is supplied."""
    print(message, flush=True)


def _artifact_saver(output_dir, on_artifact):
    """Use the caller's writer, or write ordinary JSON files in output_dir."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if on_artifact is not None:
        return on_artifact

    def save(value, filename):
        (directory / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    return save


def load_dataset(deployment, dataset, *, on_progress=_print_progress):
    """Replace the four travel collections and check acknowledged write counts.

    The caller owns deployment startup and shutdown. Partial loads are not rolled
    back. Raise RuntimeError if writes are uncertain or counts do not match.
    """
    backend = deployment.backend
    for collection, documents in dataset.items():
        ref = (
            MongoCollectionRef("travel", collection)
            if backend == "mongodb"
            else CouchbaseCollectionRef("travel", "_default", collection)
        )
        on_progress(f"[{backend}] Loading {len(documents):,} documents into travel.{collection}...")
        result = load_documents(documents, target=deployment, collection=ref, mode="replace")
        if result.uncertain_writes or sum(result.destinations.values()) != len(documents):
            raise RuntimeError(f"Incomplete load: {backend}.{collection}")
        on_progress(f"[{backend}] Loaded travel.{collection}.")


def create_indexes(deployment, indexes, *, on_progress=_print_progress):
    """Create the supplied baseline indexes in travel and close native clients.

    indexes is the collection-to-fields mapping for this backend. The deployment
    must already be running. Driver and index-definition errors propagate.
    """
    backend = deployment.backend
    on_progress(f"[{backend}] Creating baseline indexes...")
    if backend == "mongodb":
        with MongoClient(deployment.uri) as client:
            ensure_mongodb_indexes(client["travel"], indexes)
    else:
        cluster = Cluster(
            deployment.uri,
            ClusterOptions(PasswordAuthenticator(deployment.username, deployment.password)),
        )
        try:
            ensure_couchbase_indexes(cluster.bucket("travel").scope("_default"), indexes)
        finally:
            cluster.close()
    on_progress(f"[{backend}] Baseline indexes ready.")


def prepare_databases(
    params,
    *,
    run_id,
    indexes,
    output_dir,
    on_progress=_print_progress,
    on_artifact=None,
    on_metrics=None,
):
    """Generate and load travel data into two sequential, stopped deployments.

    Args:
        params: Complete nested preparation configuration, with no implicit defaults.
        run_id: Caller-selected suffix for deployment names and manifest identity.
        indexes: Backend-to-collection-to-fields index definitions.
        output_dir: Directory for JSON artifacts when on_artifact is omitted.
        on_progress: Receives progress strings. Defaults to flushed console output.
        on_artifact: Optional synchronous callback(value, filename) that saves JSON.
            It replaces the default JSON writer; it must not mutate its inputs.
        on_metrics: Optional synchronous callback receiving the final metric dict.

    Returns:
        The ready preparation manifest. The format and experiment_id field remain
        compatible with existing runs; run_id need not be a Yanex experiment ID.

    Failures save a failed manifest and propagate. Created deployments are stopped
    but retained, including partial data. Run preparation separately from benchmarks.
    """
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a nonempty string")
    save_artifact = _artifact_saver(output_dir, on_artifact)
    on_progress(f"Generating travel dataset (SF={params['scale_factor']})...")
    dataset = generate_travel_dataset(
        scale=params["scale_factor"], seed=params["seed"], reference_date=params["reference_date"]
    )

    on_progress(f"Generated {sum(map(len, dataset.values())):,} documents.")

    suffix = run_id

    # Each preparation owns fresh deployments based on the experiment ID. Later runs refer to these names.
    manifest = {
        "schema_version": 1,
        "status": "preparing",
        "experiment_id": run_id,
        "database": "travel",
        "scope": "_default",
        "document_counts": {name: len(rows) for name, rows in dataset.items()},
        "deployments": {},
    }
    save_artifact(indexes, "indexes.json")
    save_artifact(manifest, "preparation.json")

    try:
        for backend in ("mongodb", "couchbase"):
            name = f"jsonbench-{backend}-{suffix}"
            manifest["deployments"][backend] = {"name": name, "status": "creating"}
            save_artifact(manifest, "preparation.json")

            deployment = None
            try:
                # deploy the backend-specific database instance
                on_progress(f"[{backend}] Deploying {name}...")
                if backend == "mongodb":
                    deployment = deploy_mongodb(
                        name,
                        port=params["mongodb"]["port"],
                        version=params["mongodb"]["version"],
                        memory_limit_mb=params[backend]["memory_limit_mb"],
                        wiredtiger_cache_size_gb=params["mongodb"]["wiredtiger_cache_size_gb"],
                    )
                else:
                    deployment = deploy_couchbase(
                        name,
                        bucket="travel",
                        edition="community",
                        version=params["couchbase"]["version"],
                        management_port=params["couchbase"]["management_port"],
                        query_port=params["couchbase"]["query_port"],
                        kv_port=params["couchbase"]["kv_port"],
                        memory_limit_mb=params[backend]["memory_limit_mb"],
                    )
                    on_progress("[couchbase] Configuring memory quotas...")
                    configure_couchbase(deployment, params["couchbase"])

                on_progress(f"[{backend}] Deployment ready.")
                manifest["deployments"][backend]["image"] = deployment.image

                load_dataset(deployment, dataset, on_progress=on_progress)
                create_indexes(deployment, indexes[backend], on_progress=on_progress)
            finally:
                # Startup can fail after BONDI saves the deployment. Stop that too.
                if deployment is None:
                    try:
                        deployment = get_deployment(name)
                    except (ValueError, FileNotFoundError):
                        pass
                if deployment is not None:
                    try:
                        on_progress(f"[{backend}] Stopping {name} (keeping data)...")
                    finally:
                        deployment.stop()
                    on_progress(f"[{backend}] Stopped.")
                    manifest["deployments"][backend]["status"] = "stopped"
            save_artifact(manifest, "preparation.json")

    except BaseException as error:
        on_progress(f"Preparation failed ({type(error).__name__}).")
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        save_artifact(manifest, "preparation.json")
        raise

    manifest["status"] = "ready"
    save_artifact(manifest, "preparation.json")
    if on_metrics is not None:
        on_metrics({"documents_per_backend": sum(manifest["document_counts"].values())})

    on_progress("Preparation complete. Both deployments are stopped; their data is retained.")

    for backend, deployment in manifest["deployments"].items():
        on_progress(f"  {backend}: {deployment['name']}")

    return manifest


def run_benchmark(
    manifest,
    params,
    *,
    scale_factor,
    templates,
    output_dir,
    on_progress=_print_progress,
    on_artifact=None,
    on_metrics=None,
    on_result=None,
):
    """Run one backend/client combination against a prepared deployment pair.

    Args:
        manifest: Ready preparation manifest returned by prepare_databases.
        params: Complete nested benchmark configuration, with no implicit defaults.
        scale_factor: Preparation scale factor, recorded as benchmark metadata.
        templates: Q1 through Q8 template dictionaries. Inputs are not modified.
        output_dir: Artifact directory, including streamed load_results.jsonl.
        on_progress: Receives progress strings. Defaults to flushed console output.
        on_artifact: Optional callback(value, filename) replacing JSON artifact writes.
        on_metrics: Optional callback receiving scalar summary metrics.
        on_result: Optional callback receiving each BONDI LoadResult after persistence.

    Returns:
        LoadAnalysis with run and per-query summaries. Both prepared databases are
        stopped before measurement; the selected database is stopped on exit.

    The host lock prevents concurrent benchmark calls. Observations are flushed
    during execution. Early termination saves summaries and metrics, then raises
    RuntimeError. Other failures propagate; already written observations remain.
    """
    if not manifest or manifest.get("status") != "ready":
        raise ValueError("The preparation manifest must be ready")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported preparation manifest version")
    save_artifact = _artifact_saver(output_dir, on_artifact)
    backend = params["backend"]
    if backend not in {"mongodb", "couchbase"}:
        raise ValueError("backend must be mongodb or couchbase")

    if len(templates) != 8:
        raise ValueError("Supply Q1 through Q8 in order")
    labels = [f"Q{i}" for i in range(1, 9)]
    templates = deepcopy(templates)
    templates[3]["operations"]["match"]["itinerary.location"] = params["queries"]["q4_location"]

    # translate the queries to the respective backend representation
    queries = [
        translate_mongodb(template, database=manifest["database"])
        if backend == "mongodb"
        else translate_couchbase(template, bucket=manifest["database"], scope=manifest["scope"])
        for template in templates
    ]

    # wrap in a Workload object
    workload = Workload([WorkloadEntry(query) for query in queries])

    # set up selection strategy for load generator: we use WeightedRandom
    selection = WeightedRandom(weights=params["load"]["weights"], seed=params["seed"])

    # get the deployment names for the backends specified in the prepare manifest
    deployments = {
        key: get_deployment(value["name"]) for key, value in manifest["deployments"].items()
    }
    deployment = deployments[backend]

    save_artifact(templates, "templates.json")
    save_artifact([json.loads(query.to_json()) for query in queries], "queries.json")
    save_artifact(
        {
            "prepare_id": manifest["experiment_id"],
            "scale_factor": scale_factor,
            "deployment": deployment.name,
            "query_labels": labels,
        },
        "benchmark.json",
    )

    # One host runs one benchmark at a time, even across preparation dependencies.
    # This lock coordinates this script only; run preparation separately.
    lock_path = Path(tempfile.gettempdir()) / "bondi-json-bench-benchmark.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another benchmark is running. Run the sweep sequentially."
            ) from None

        on_progress(
            f"Using preparation {manifest['experiment_id']}; backend={backend}, clients={params['clients']}.",
        )
        # Stop only the deployments owned by this dependency. Never remove their data.
        for other in deployments.values():
            on_progress(f"Stopping {other.name} before the run...")
            other.stop()
        try:
            on_progress(f"Starting {deployment.name}...")
            deployment.start(timeout=params["deployment"]["startup_timeout_seconds"])
            executor_type = MongoExecutor if backend == "mongodb" else CouchbaseExecutor
            credentials = (
                {}
                if backend == "mongodb"
                else {
                    "username": deployment.username,
                    "password": deployment.password,
                }
            )
            with executor_type.from_uri(
                deployment.uri,
                **credentials,
                concurrency=params["clients"],
                continue_on_error=True,
                **params["executor"],
            ) as executor:
                # Flush each observation so completed attempts survive an interrupted run.
                artifacts = Path(output_dir)
                artifacts.mkdir(parents=True, exist_ok=True)
                with (artifacts / "load_results.jsonl").open("w", buffering=1) as output:
                    on_progress("Generating load (warm-up, measurement, then drain)...")

                    def record_result(result):
                        output.write(json.dumps(load_result_record(result)) + "\n")
                        if on_result is not None:
                            on_result(result)

                    results = executor.generate_load(
                        workload,
                        selection=selection,
                        warmup_seconds=params["load"]["warmup_seconds"],
                        measurement_seconds=params["load"]["measurement_seconds"],
                        drain_timeout_seconds=params["load"]["drain_timeout_seconds"],
                        collect_results=False,
                        return_load_results=True,
                        on_result=record_result,
                    )
            analysis = analyse_load_results(
                results,
                query_labels=labels,
                warmup_seconds=params["load"]["warmup_seconds"],
                measurement_seconds=params["load"]["measurement_seconds"],
            )
            summary = asdict(analysis.summary)
            save_artifact(summary, "summary.json")
            save_artifact([asdict(query) for query in analysis.queries], "per_query.json")
            if on_metrics is not None:
                on_metrics(
                    {
                        key: value
                        for key, value in summary.items()
                        if isinstance(value, (int, float))
                    }
                )
            on_progress(json.dumps(summary, indent=2))
            if analysis.summary.early_terminated:
                raise RuntimeError("Load generation stopped early; partial results were saved")
        finally:
            try:
                on_progress(f"Stopping {deployment.name} (keeping data)...")
            finally:
                deployment.stop()

    return analysis
