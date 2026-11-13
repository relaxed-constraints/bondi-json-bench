"""Run one backend/client combination against a prepared Yanex dependency."""

import fcntl
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import yanex
from bondi.couchbase import CouchbaseExecutor
from bondi.deployment import get_deployment
from bondi.load import WeightedRandom
from bondi.mongodb import MongoExecutor
from bondi.workload import Workload, WorkloadEntry

from json_bench.analysis import analyse_load_results, load_result_record
from json_bench.queries import load_template, translate_couchbase, translate_mongodb


def main():
    # load the manifest from the preparation experiment dependency
    prepare = yanex.get_dependency("prepare")
    if prepare is None:
        raise ValueError("Supply a preparation experiment with -D prepare=<experiment-id>")
    manifest = prepare.load_artifact("preparation.json")
    if prepare.status != "completed" or not manifest or manifest.get("status") != "ready":
        raise ValueError("The prepare dependency must have completed database preparation")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported preparation manifest version")

    # load yanex parameters
    params = yanex.get_params()

    backend = params["backend"]
    if backend not in {"mongodb", "couchbase"}:
        raise ValueError("backend must be mongodb or couchbase")

    # load 8 query templates from files
    labels = [f"Q{i}" for i in range(1, 9)]
    template_dir = Path(__file__).with_name("templates")
    templates = [load_template(template_dir / f"q{i}.json") for i in range(1, 9)]
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

    yanex.save_artifact(templates, "templates.json")
    yanex.save_artifact([json.loads(query.to_json()) for query in queries], "queries.json")
    yanex.save_artifact(
        {
            "prepare_id": prepare.id,
            "scale_factor": prepare.get_param("scale_factor"),
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

        print(
            f"Using preparation {prepare.id}; backend={backend}, clients={params['clients']}.",
            flush=True,
        )
        # Stop only the deployments owned by this dependency. Never remove their data.
        for other in deployments.values():
            print(f"Stopping {other.name} before the run...", flush=True)
            other.stop()
        try:
            print(f"Starting {deployment.name}...", flush=True)
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
                artifacts = yanex.get_artifacts_dir()
                artifacts.mkdir(parents=True, exist_ok=True)
                with (artifacts / "load_results.jsonl").open("w", buffering=1) as output:
                    print("Generating load (warm-up, measurement, then drain)...", flush=True)
                    results = executor.generate_load(
                        workload,
                        selection=selection,
                        warmup_seconds=params["load"]["warmup_seconds"],
                        measurement_seconds=params["load"]["measurement_seconds"],
                        drain_timeout_seconds=params["load"]["drain_timeout_seconds"],
                        collect_results=False,
                        return_load_results=True,
                        on_result=lambda result: output.write(
                            json.dumps(load_result_record(result)) + "\n"
                        ),
                    )
            analysis = analyse_load_results(
                results,
                query_labels=labels,
                warmup_seconds=params["load"]["warmup_seconds"],
                measurement_seconds=params["load"]["measurement_seconds"],
            )
            summary = asdict(analysis.summary)
            yanex.save_artifact(summary, "summary.json")
            yanex.save_artifact([asdict(query) for query in analysis.queries], "per_query.json")
            yanex.log_metrics(
                {key: value for key, value in summary.items() if isinstance(value, (int, float))}
            )
            print(json.dumps(summary, indent=2), flush=True)
            if analysis.summary.early_terminated:
                raise RuntimeError("Load generation stopped early; partial results were saved")
        finally:
            print(f"Stopping {deployment.name} (keeping data)...", flush=True)
            deployment.stop()


if __name__ == "__main__":
    main()
