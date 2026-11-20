"""Opt-in seeded operator-combination check on disposable deployments.

Run with JSONBENCH_LIVE=1 uv run pytest tests/test_operator_combinations_live.py -q.
Requires Docker and free ports 27137, 18391, 18393 and 21330.
"""

import json
import os
from uuid import uuid4

import pytest
from bondi.couchbase import CouchbaseCollectionRef, CouchbaseExecutor, CouchbaseQuery
from bondi.data import load_documents
from bondi.deployment import deploy_couchbase, deploy_mongodb
from bondi.mongodb import MongoCollectionRef, MongoExecutor
from couchbase.n1ql import QueryScanConsistency

from json_bench.queries import translate_couchbase, translate_mongodb


def canonical(rows, template, backend):
    """Normalise only known backend output shapes, preserving row multiplicity."""
    import copy

    ops = template["operations"]
    output = []
    for original in rows:
        row = copy.deepcopy(original)
        if "group" in ops:
            if backend == "mongodb":
                by = ops["group"]["by"]
                key = row.pop("_id")
                if isinstance(key, dict):
                    row.update(key)
                else:
                    row[by.replace(".", "_")] = key
        elif "project" in ops:
            if backend == "mongodb":
                projected = {}
                for path in ops["project"]:
                    value = row
                    for part in path.split("."):
                        value = value[part]
                    projected[path.replace(".", "_")] = value
                row = projected
        elif backend == "couchbase":
            document = row["tours"]
            if "join" in ops:
                document["bookings"] = row["bookings"]
            if "unnest" in ops:
                document["itinerary"] = row["__unnest_0"]
            row = document
        output.append(row)
    return output


def comparable(rows, ordered):
    """Keep ordered rows; otherwise sort serialised rows without removing duplicates."""
    values = [json.dumps(row, sort_keys=True) for row in rows]
    return values if ordered else sorted(values)


@pytest.mark.skipif(os.environ.get("JSONBENCH_LIVE") != "1", reason="requires local Docker")
def test_operator_combinations_live():
    from template_cases import DATA, generated_templates, named_templates

    name = "operators-" + uuid4().hex[:8]
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
        for collection, documents in DATA.items():
            load_documents(
                documents,
                connection=mongo.connection,
                collection=MongoCollectionRef("travel", collection),
            )
            load_documents(
                documents,
                connection=couch.connection,
                collection=CouchbaseCollectionRef("travel", "_default", collection),
            )
        cases = [
            (name, {"primary_collection": "tours", "operations": ops}, expected)
            for name, ops, expected in named_templates()
        ]
        cases += [
            (f"seed23-{i}", template, None) for i, template in enumerate(generated_templates())
        ]
        with (
            MongoExecutor.from_connection(mongo.connection, timeout_seconds=60) as m,
            CouchbaseExecutor.from_connection(couch.connection, timeout_seconds=60) as c,
        ):
            for statement in [
                "CREATE PRIMARY INDEX ON `tours`;",
                "CREATE INDEX `bookings-tour_id` ON `bookings`(`tour_id`);",
            ]:
                c.run(CouchbaseQuery(statement, query_context="default:`travel`.`_default`"))
            for label, template, expected in cases:
                mongo_query = translate_mongodb(template, database="travel")
                couch_query = translate_couchbase(template, bucket="travel")
                left = canonical(
                    m.run(mongo_query, collect_results=True).documents, template, "mongodb"
                )
                right = canonical(
                    c.run(
                        couch_query,
                        collect_results=True,
                        query_kwargs={"scan_consistency": QueryScanConsistency.REQUEST_PLUS},
                    ).documents,
                    template,
                    "couchbase",
                )
                ordered = "sort" in template["operations"]
                detail = f"{label}: {json.dumps(template)}"
                assert comparable(left, ordered) == comparable(right, ordered), detail
                if expected is not None:
                    assert comparable(left, ordered) == comparable(expected, ordered), detail
    finally:
        if couch is not None:
            couch.remove()
        if mongo is not None:
            mongo.remove()
