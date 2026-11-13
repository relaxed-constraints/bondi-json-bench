"""Prepare two stopped, populated databases for dependent Yanex experiments."""

import json
from pathlib import Path

import yanex
from bondi.couchbase import CouchbaseCollectionRef
from bondi.data import load_documents
from bondi.deployment import deploy_couchbase, deploy_mongodb, get_deployment
from bondi.mongodb import MongoCollectionRef
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from pymongo import MongoClient

from json_bench.data import generate_travel_dataset
from json_bench.deployment import configure_couchbase
from json_bench.indexes import ensure_couchbase_indexes, ensure_mongodb_indexes


def main():

    # load parameters and indexes
    params = yanex.get_params()
    indexes = json.loads(Path(__file__).with_name("indexes.json").read_text())

    print(f"Generating travel dataset (SF={params['scale_factor']})...", flush=True)
    dataset = generate_travel_dataset(
        scale=params["scale_factor"], seed=params["seed"], reference_date=params["reference_date"]
    )

    print(f"Generated {sum(map(len, dataset.values())):,} documents.", flush=True)

    suffix = yanex.get_experiment_id()

    # Each preparation owns fresh deployments based on the experiment ID. Later runs refer to these names.
    manifest = {
        "schema_version": 1,
        "status": "preparing",
        "experiment_id": yanex.get_experiment_id(),
        "database": "travel",
        "scope": "_default",
        "document_counts": {name: len(rows) for name, rows in dataset.items()},
        "deployments": {},
    }
    yanex.save_artifact(indexes, "indexes.json")
    yanex.save_artifact(manifest, "preparation.json")

    try:
        for backend in ("mongodb", "couchbase"):
            name = f"jsonbench-{backend}-{suffix}"
            manifest["deployments"][backend] = {"name": name, "status": "creating"}
            yanex.save_artifact(manifest, "preparation.json")

            deployment = None
            try:
                # deploy the backend-specific database instance
                print(f"[{backend}] Deploying {name}...", flush=True)
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
                    print("[couchbase] Configuring memory quotas...", flush=True)
                    configure_couchbase(deployment, params["couchbase"])

                print(f"[{backend}] Deployment ready.", flush=True)
                manifest["deployments"][backend]["image"] = deployment.image

                # load the dataset
                for collection, documents in dataset.items():
                    ref = (
                        MongoCollectionRef("travel", collection)
                        if backend == "mongodb"
                        else CouchbaseCollectionRef("travel", "_default", collection)
                    )
                    print(
                        f"[{backend}] Loading {len(documents):,} documents into travel.{collection}...",
                        flush=True,
                    )
                    result = load_documents(
                        documents, target=deployment, collection=ref, mode="replace"
                    )
                    if result.uncertain_writes or sum(result.destinations.values()) != len(
                        documents
                    ):
                        raise RuntimeError(f"Incomplete load: {backend}.{collection}")
                    print(f"[{backend}] Loaded travel.{collection}.", flush=True)

                # create indexes
                print(f"[{backend}] Creating baseline indexes...", flush=True)
                if backend == "mongodb":
                    with MongoClient(deployment.uri) as client:
                        ensure_mongodb_indexes(client["travel"], indexes[backend])
                else:
                    cluster = Cluster(
                        deployment.uri,
                        ClusterOptions(
                            PasswordAuthenticator(deployment.username, deployment.password)
                        ),
                    )
                    try:
                        ensure_couchbase_indexes(
                            cluster.bucket("travel").scope("_default"), indexes[backend]
                        )
                    finally:
                        cluster.close()
                print(f"[{backend}] Baseline indexes ready.", flush=True)
            finally:
                # Startup can fail after BONDI saves the deployment. Stop that too.
                if deployment is None:
                    try:
                        deployment = get_deployment(name)
                    except (ValueError, FileNotFoundError):
                        pass
                if deployment is not None:
                    print(f"[{backend}] Stopping {name} (keeping data)...", flush=True)
                    deployment.stop()
                    print(f"[{backend}] Stopped.", flush=True)
                    manifest["deployments"][backend]["status"] = "stopped"
            yanex.save_artifact(manifest, "preparation.json")

    except BaseException as error:
        print(f"Preparation failed ({type(error).__name__}).", flush=True)
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        yanex.save_artifact(manifest, "preparation.json")
        raise

    manifest["status"] = "ready"
    yanex.save_artifact(manifest, "preparation.json")
    yanex.log_metrics({"documents_per_backend": sum(manifest["document_counts"].values())})

    print("Preparation complete. Both deployments are stopped; their data is retained.")

    for backend, deployment in manifest["deployments"].items():
        print(f"  {backend}: {deployment['name']}")


if __name__ == "__main__":
    main()
