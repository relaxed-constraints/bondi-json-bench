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
        lambda q: q["operations"]["group"].update({"aggregates": {"total": "count(*)"}}),
        lambda q: q["operations"]["group"].update(
            {"aggregates": {"total": "sum(avg(travellers))"}}
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


Q2 = json.loads((Path(__file__).parent / "fixtures" / "q2_translation.json").read_text())


def test_q2_matches_corrected_jsonbench():
    template = copy.deepcopy(Q2["template"])
    assert translate_mongodb(template, database="travel").pipeline == Q2["mongodb_pipeline"]
    query = translate_couchbase(template, bucket="travel")
    assert query.statement == Q2["couchbase_statement"]
    assert query.query_context == "default:`travel`.`_default`"
    assert template == Q2["template"]


def test_string_unnest_matches_dictionary_form():
    template = copy.deepcopy(Q2["template"])
    template["operations"]["unnest"] = ["travellers"]
    assert translate_mongodb(template, database="travel").pipeline == Q2["mongodb_pipeline"]
    assert translate_couchbase(template, bucket="travel").statement == Q2["couchbase_statement"]


@pytest.mark.parametrize(
    "unnest",
    [
        "travellers",
        [None],
        [{}],
        [{"field": "travellers", "from": "users"}],
        ["travellers..age"],
        [{"field": "travellers", "extra": True}],
    ],
)
@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
def test_invalid_unnest(unnest, backend):
    template = copy.deepcopy(Q2["template"])
    template["operations"]["unnest"] = unnest
    with pytest.raises(ValueError):
        if backend == "mongodb":
            translate_mongodb(template, database="travel")
        else:
            translate_couchbase(template, bucket="travel")


def test_nested_unnest_resolves_aliases_in_order():
    template = copy.deepcopy(Q2["template"])
    template["operations"]["unnest"].append("travellers.children")
    template["operations"]["group"]["aggregates"] = {"age": " AVG( travellers.children.age ) "}
    mongo = translate_mongodb(template, database="travel")
    assert mongo.pipeline[:2] == [{"$unwind": "$travellers"}, {"$unwind": "$travellers.children"}]
    couch = translate_couchbase(template, bucket="travel").statement
    assert "AVG(`__unnest_1`.`age`)" in couch
    assert "UNNEST `__unnest_0`.`children` AS `__unnest_1`" in couch


def test_unnest_alias_does_not_collide_with_collection():
    template = copy.deepcopy(Q2["template"])
    template["primary_collection"] = "__unnest_0"
    template["operations"]["unnest"] = ["travellers"]
    assert "AVG(`__unnest_0_`.`age`)" in translate_couchbase(template, bucket="travel").statement


Q3 = json.loads((Path(__file__).parent / "fixtures" / "q3_translation.json").read_text())


def test_q3_matches_corrected_jsonbench():
    template = copy.deepcopy(Q3["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q3["mongodb_pipeline"]
    assert mongo.target == MongoCollectionRef("travel", "bookings")
    assert couch.statement == Q3["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert template == Q3["template"]
    assert MongoAggregateQuery.from_json(mongo.to_json()) == mongo
    assert CouchbaseQuery.from_json(couch.to_json()) == couch


@pytest.mark.parametrize("aggregate", ["sum", "avg", "min", "max"])
def test_size_of_nested_field(aggregate):
    template = copy.deepcopy(Q3["template"])
    template["operations"]["group"]["aggregates"] = {
        "value": f" {aggregate.upper()}( SIZE( details.travellers ) ) "
    }
    mongo = translate_mongodb(template, database="travel")
    assert mongo.pipeline[0]["$group"]["value"] == {
        "$" + aggregate: {"$size": "$details.travellers"}
    }
    assert f"{aggregate.upper()}(ARRAY_LENGTH(`bookings`.`details`.`travellers`))" in (
        translate_couchbase(template, bucket="travel").statement
    )


@pytest.mark.parametrize(
    "expression",
    [
        "avg(size())",
        "avg(size(size(travellers)))",
        "avg(avg(travellers))",
        "size(travellers)",
        "avg(size(travellers), 2)",
        "avg(size(travellers); DROP)",
    ],
)
@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
def test_invalid_nested_expression(expression, backend):
    template = copy.deepcopy(Q3["template"])
    template["operations"]["group"]["aggregates"] = {"value": expression}
    with pytest.raises(ValueError):
        if backend == "mongodb":
            translate_mongodb(template, database="travel")
        else:
            translate_couchbase(template, bucket="travel")


def test_size_resolves_unnested_field():
    template = copy.deepcopy(Q3["template"])
    template["operations"]["unnest"] = ["travellers"]
    template["operations"]["group"]["aggregates"] = {"value": "avg(size(travellers.children))"}
    assert "AVG(ARRAY_LENGTH(`__unnest_0`.`children`))" in (
        translate_couchbase(template, bucket="travel").statement
    )
