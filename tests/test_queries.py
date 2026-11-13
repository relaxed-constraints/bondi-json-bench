"""Compare Q1 translation with captured corrected JSONBench output."""

import copy
import json
from pathlib import Path

import pytest
from bondi.couchbase import CouchbaseQuery
from bondi.mongodb import MongoAggregateQuery, MongoCollectionRef

from json_bench.queries import translate_couchbase, translate_mongodb

REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "q1_translation.json").read_text())


@pytest.fixture
def template():
    return copy.deepcopy(REFERENCE["template"])


def test_q1_matches_corrected_jsonbench(template):
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert isinstance(mongo, MongoAggregateQuery)
    assert mongo.target == MongoCollectionRef("travel", "bookings")
    assert mongo.pipeline == REFERENCE["mongodb_pipeline"]
    assert isinstance(couch, CouchbaseQuery)
    assert couch.statement == REFERENCE["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert couch.named_parameters == {}
    assert couch.positional_parameters == []


def test_translation_is_independent_and_does_not_mutate(template):
    before = copy.deepcopy(template)
    first = translate_mongodb(template, database="travel")
    translate_couchbase(template, bucket="travel", scope="research")
    assert template == before
    first.pipeline[0]["$group"]["total_revenue"] = 0
    assert translate_mongodb(template, database="travel").pipeline == REFERENCE["mongodb_pipeline"]


def test_destination_does_not_rewrite_statement(template):
    query = translate_couchbase(template, bucket="other", scope="research")
    assert query.statement == REFERENCE["couchbase_statement"]
    assert query.query_context == "default:`other`.`research`"


@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
@pytest.mark.parametrize(
    "change",
    [
        lambda q: q["operations"].update({"match": {"paid": True}}),
        lambda q: q["operations"].update({"join": []}),
        lambda q: q["operations"]["group"].update({"by": ["tour_id"]}),
        lambda q: q["operations"]["group"].update({"by": "tour._id"}),
        lambda q: q["operations"]["group"].update({"aggregates": {}}),
        lambda q: q["operations"]["group"].update({"aggregates": {"total": "avg(total_price)"}}),
        lambda q: q["operations"]["group"].update(
            {"aggregates": {"total": "sum(size(travellers))"}}
        ),
        lambda q: q["operations"]["group"].update({"aggregates": {"_id": "sum(total_price)"}}),
        lambda q: q["operations"]["group"].update({"aggregates": {"tour_id": "sum(total_price)"}}),
        lambda q: q.update({"primary_collection": "bookings; DROP"}),
    ],
)
def test_unsupported_templates_fail_explicitly(template, change, backend):
    change(template)
    with pytest.raises(ValueError):
        if backend == "mongodb":
            translate_mongodb(template, database="travel")
        else:
            translate_couchbase(template, bucket="travel")


@pytest.mark.parametrize("value", [None, [], "template"])
def test_invalid_template_type(value):
    with pytest.raises(TypeError, match="dictionary"):
        translate_mongodb(value, database="travel")


def test_aggregate_type_and_whitespace(template):
    template["operations"]["group"]["aggregates"]["total_revenue"] = " SUM( total_price ) "
    assert translate_mongodb(template, database="travel").pipeline == REFERENCE["mongodb_pipeline"]
    assert (
        translate_couchbase(template, bucket="travel").statement == REFERENCE["couchbase_statement"]
    )
    template["operations"]["group"]["aggregates"]["total_revenue"] = 1
    with pytest.raises(TypeError, match="string"):
        translate_couchbase(template, bucket="travel")


@pytest.mark.parametrize("key", ["database", "bucket", "scope"])
def test_invalid_destination(template, key):
    with pytest.raises(ValueError, match="simple identifier"):
        if key == "database":
            translate_mongodb(template, database="bad.name")
        else:
            translate_couchbase(template, **{"bucket": "travel", key: "bad.name"})


def test_bondi_serialization_round_trip(template):
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert MongoAggregateQuery.from_json(mongo.to_json()) == mongo
    assert CouchbaseQuery.from_json(couch.to_json()) == couch
