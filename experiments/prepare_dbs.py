"""Prepare two stopped, populated databases for dependent Yanex experiments."""

import json
import uuid
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

DEFAULTS = {
    "scale_factor": 0.1,
    "seed": 23,
    "reference_date": "2025-11-01",
    "memory_limit_mb": 24576,
    "wiredtiger_cache_size_gb": 12,
    "couchbase_data_mb": 8192,
    "couchbase_index_mb": 4096,
    "mongodb_version": "8.2.1",
    "couchbase_version": "8.0.0",
    "mongodb_port": 27147,
    "couchbase_management_port": 18491,
    "couchbase_query_port": 18493,
    "couchbase_kv_port": 21430,
}


def main():
    config = {key: yanex.get_param(key, default=value) for key, value in DEFAULTS.items()}
    indexes = json.loads(Path(__file__).with_name("indexes.json").read_text())
    dataset = generate_travel_dataset(
        scale=config["scale_factor"], seed=config["seed"], reference_date=config["reference_date"]
    )
    # Each preparation owns fresh deployments. Later runs refer to these names.
    suffix = uuid.uuid4().hex[:12]
    manifest = {
        "schema_version": 1,
        "status": "preparing",
        "experiment_id": yanex.get_experiment_id(),
        "config": config,
        "database": "travel",
        "scope": "_default",
        "document_counts": {name: len(rows) for name, rows in dataset.items()},
        "deployments": {},
    }
    yanex.save_artifact(config, "resolved_config.json")
    yanex.save_artifact(indexes, "indexes.json")
    yanex.save_artifact(manifest, "preparation.json")
    try:
        for backend in ("mongodb", "couchbase"):
            name = f"jsonbench-{backend}-{suffix}"
            manifest["deployments"][backend] = {"name": name, "status": "creating"}
            yanex.save_artifact(manifest, "preparation.json")
            deployment = None
            try:
                if backend == "mongodb":
                    deployment = deploy_mongodb(
                        name,
                        port=config["mongodb_port"],
                        version=config["mongodb_version"],
                        memory_limit_mb=config["memory_limit_mb"],
                        wiredtiger_cache_size_gb=config["wiredtiger_cache_size_gb"],
                    )
                else:
                    deployment = deploy_couchbase(
                        name,
                        bucket="travel",
                        edition="community",
                        version=config["couchbase_version"],
                        management_port=config["couchbase_management_port"],
                        query_port=config["couchbase_query_port"],
                        kv_port=config["couchbase_kv_port"],
                        memory_limit_mb=config["memory_limit_mb"],
                    )
                    configure_couchbase(deployment, config)
                manifest["deployments"][backend]["image"] = deployment.image
                for collection, documents in dataset.items():
                    ref = (
                        MongoCollectionRef("travel", collection)
                        if backend == "mongodb"
                        else CouchbaseCollectionRef("travel", "_default", collection)
                    )
                    result = load_documents(documents, target=deployment, collection=ref)
                    if result.uncertain_writes or sum(result.destinations.values()) != len(
                        documents
                    ):
                        raise RuntimeError(f"Incomplete load: {backend}.{collection}")
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
            finally:
                # Startup can fail after BONDI saves the deployment. Stop that too.
                if deployment is None:
                    try:
                        deployment = get_deployment(name)
                    except (ValueError, FileNotFoundError):
                        pass
                if deployment is not None:
                    deployment.stop()
                    manifest["deployments"][backend]["status"] = "stopped"
            yanex.save_artifact(manifest, "preparation.json")
    except BaseException as error:
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
