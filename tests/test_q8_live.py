"""Opt-in Q8 integration check on disposable deployments.

Run with JSONBENCH_LIVE=1 uv run pytest tests/test_q8_live.py -q.
Requires Docker and free ports 27137, 18391, 18393 and 21330.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from bondi.couchbase import CouchbaseCollectionRef, CouchbaseExecutor, CouchbaseQuery
from bondi.data import load_documents
from bondi.deployment import deploy_couchbase, deploy_mongodb
from bondi.mongodb import MongoCollectionRef, MongoExecutor
from couchbase.n1ql import QueryScanConsistency

from json_bench.queries import translate_couchbase, translate_mongodb
from json_bench.validate import compare_results


@pytest.mark.skipif(os.environ.get("JSONBENCH_LIVE") != "1", reason="requires local Docker")
def test_q8_weighted_join_live():
    fixtures = Path(__file__).parent / "fixtures"
    data = json.loads((fixtures / "q8_weighted_data.json").read_text())
    template = json.loads((fixtures / "q8_translation.json").read_text())["template"]
    name = "q8-check-" + uuid4().hex[:8]
    expected = {(r["destination"], r["nationality"]): r["avg_rating"] for r in data["expected"]}
    mongo = couch = None
    try:
        mongo = deploy_mongodb(name=name + "-mongo", port=27137)
        couch = deploy_couchbase(
            name=name + "-cb",
            management_port=18391,
            query_port=18393,
            kv_port=21330,
            bucket="travel",
        )
        for collection in ["tours", "bookings", "reviews"]:
            load_documents(
                data[collection], target=mongo, collection=MongoCollectionRef("travel", collection)
            )
            load_documents(
                data[collection],
                target=couch,
                collection=CouchbaseCollectionRef("travel", "_default", collection),
            )
        with MongoExecutor.from_uri(mongo.uri, timeout_seconds=60) as executor:
            result = executor.run(
                translate_mongodb(template, database="travel"), collect_results=True
            )
            assert {
                (r["_id"]["destination"], r["_id"]["bookings_travellers_nationality"]): r[
                    "avg_rating"
                ]
                for r in result.documents
            } == pytest.approx(expected)
        mongo_result = result
        query = translate_couchbase(template, bucket="travel")
        with CouchbaseExecutor.from_uri(
            couch.uri, username=couch.username, password=couch.password, timeout_seconds=60
        ) as executor:
            for name, collection, field in [
                ("tours-id", "tours", "_id"),
                ("reviews-tour_id", "reviews", "tour_id"),
                ("bookings-tour_id", "bookings", "tour_id"),
            ]:
                executor.run(
                    CouchbaseQuery(
                        f"CREATE INDEX `{name}` ON `{collection}`(`{field}`);",
                        query_context=query.query_context,
                    )
                )
            result = executor.run(
                query,
                collect_results=True,
                query_kwargs={"scan_consistency": QueryScanConsistency.REQUEST_PLUS},
            )
            assert {
                (r["destination"], r["bookings_travellers_nationality"]): r["avg_rating"]
                for r in result.documents
            } == pytest.approx(expected)
        compare_results(template, mongo_result, result)
    finally:
        if couch is not None:
            couch.remove()
        if mongo is not None:
            mongo.remove()
