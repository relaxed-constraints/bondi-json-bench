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
    assert mongo.collection == MongoCollectionRef("travel", "bookings")
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
        lambda q: q["operations"].update({"match": {"paid": None}}),
        lambda q: q["operations"].update({"join": {}}),
        lambda q: q["operations"]["group"].update({"by": []}),
        lambda q: q["operations"]["group"].update({"by": "tour.._id"}),
        lambda q: q["operations"]["group"].update({"aggregates": []}),
        lambda q: q["operations"]["group"].update({"aggregates": {"total": "count(total_price)"}}),
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
    assert mongo.collection == MongoCollectionRef("travel", "bookings")
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


Q4 = json.loads((Path(__file__).parent / "fixtures" / "q4_translation.json").read_text())


def test_q4_matches_corrected_jsonbench():
    template = copy.deepcopy(Q4["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q4["mongodb_pipeline"]
    assert mongo.collection == MongoCollectionRef("travel", "tours")
    assert couch.statement == Q4["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert template == Q4["template"]
    mongo.pipeline[1]["$match"]["itinerary.location"] = "changed"
    assert template == Q4["template"]


@pytest.mark.parametrize("value", [None, [], {}, float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
def test_invalid_match_value(value, backend):
    template = copy.deepcopy(Q4["template"])
    template["operations"]["match"] = {"itinerary.location": value}
    with pytest.raises(ValueError):
        if backend == "mongodb":
            translate_mongodb(template, database="travel")
        else:
            translate_couchbase(template, bucket="travel")


def test_match_literals_and_conjunction():
    template = copy.deepcopy(Q4["template"])
    values = {
        "itinerary.location": 'A "quoted" place\\north',
        "active": True,
        "rank": 3,
        "score": 1.5,
    }
    template["operations"]["match"] = values
    mongo = translate_mongodb(template, database="travel")
    assert mongo.pipeline[1] == {"$match": values}
    statement = translate_couchbase(template, bucket="travel").statement
    assert (
        f"WHERE `__unnest_0`.`location` = {json.dumps(values['itinerary.location'])}" in statement
    )
    assert (
        " AND `tours`.`active` = true AND `tours`.`rank` = 3 AND `tours`.`score` = 1.5" in statement
    )


@pytest.mark.parametrize("value", [[], None, {"bad..path": "x"}, {"$where": "x"}])
def test_invalid_match_structure(value):
    template = copy.deepcopy(Q4["template"])
    template["operations"]["match"] = value
    for translate, target in [
        (translate_mongodb, {"database": "travel"}),
        (translate_couchbase, {"bucket": "travel"}),
    ]:
        with pytest.raises(ValueError):
            translate(template, **target)


def test_empty_match_and_count_whitespace():
    template = copy.deepcopy(Q4["template"])
    template["operations"]["match"] = {}
    template["operations"]["group"]["aggregates"] = {"num_of_tours": " COUNT( * ) "}
    assert translate_mongodb(template, database="travel").pipeline[1] == {"$match": {}}
    statement = translate_couchbase(template, bucket="travel").statement
    assert "COUNT(*)" in statement and "WHERE" not in statement


Q5 = json.loads((Path(__file__).parent / "fixtures" / "q5_translation.json").read_text())


def test_q5_matches_corrected_jsonbench():
    template = copy.deepcopy(Q5["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q5["mongodb_pipeline"]
    assert mongo.collection == MongoCollectionRef("travel", "tours")
    assert couch.statement == Q5["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    mongo.pipeline[0]["$lookup"]["foreignField"] = "changed"
    assert template == Q5["template"]


@pytest.mark.parametrize(
    "join",
    [
        None,
        {},
        "reviews",
        {"from": "reviews"},
        {"from": "tours", "localField": "_id", "foreignField": "tour_id"},
        {"from": "bad.name", "localField": "_id", "foreignField": "tour_id"},
        {"from": "reviews", "localField": "$bad", "foreignField": "tour_id"},
        {"from": "reviews", "localField": "_id", "foreignField": "tour..id"},
    ],
)
@pytest.mark.parametrize("backend", ["mongodb", "couchbase"])
def test_invalid_join(join, backend):
    template = copy.deepcopy(Q5["template"])
    template["operations"]["join"] = join
    with pytest.raises(ValueError):
        if backend == "mongodb":
            translate_mongodb(template, database="travel")
        else:
            translate_couchbase(template, bucket="travel")


def test_join_list_and_duplicate_sources():
    template = copy.deepcopy(Q5["template"])
    join = template["operations"]["join"]
    template["operations"]["join"] = [join]
    assert translate_mongodb(template, database="travel").pipeline == Q5["mongodb_pipeline"]
    assert translate_couchbase(template, bucket="travel").statement == Q5["couchbase_statement"]
    template["operations"]["join"].append(copy.deepcopy(join))
    for translate, target in [
        (translate_mongodb, {"database": "travel"}),
        (translate_couchbase, {"bucket": "travel"}),
    ]:
        with pytest.raises(ValueError, match="distinct"):
            translate(template, **target)


def test_join_precedes_expansion_and_filter():
    template = copy.deepcopy(Q5["template"])
    template["operations"].update({"unnest": ["itinerary"], "match": {"reviews.rating": 5}})
    pipeline = translate_mongodb(template, database="travel").pipeline
    assert [next(iter(stage)) for stage in pipeline] == [
        "$lookup",
        "$unwind",
        "$unwind",
        "$match",
        "$group",
    ]
    statement = translate_couchbase(template, bucket="travel").statement
    assert (
        statement.index("JOIN")
        < statement.index("UNNEST")
        < statement.index("WHERE")
        < statement.index("GROUP BY")
    )
    assert "WHERE `reviews`.`rating` = 5" in statement
    assert "META(" not in statement


Q6 = json.loads((Path(__file__).parent / "fixtures" / "q6_translation.json").read_text())


def test_q6_matches_corrected_jsonbench():
    template = copy.deepcopy(Q6["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q6["mongodb_pipeline"]
    assert mongo.collection == MongoCollectionRef("travel", "bookings")
    assert couch.statement == Q6["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert template == Q6["template"]
    assert MongoAggregateQuery.from_json(mongo.to_json()) == mongo
    assert CouchbaseQuery.from_json(couch.to_json()) == couch


def test_dotted_group_alias_collision():
    template = copy.deepcopy(Q6["template"])
    template["operations"]["group"]["aggregates"] = {"tours_destination": "avg(travellers.age)"}
    for translate, target in [
        (translate_mongodb, {"database": "travel"}),
        (translate_couchbase, {"bucket": "travel"}),
    ]:
        with pytest.raises(ValueError, match="collide"):
            translate(template, **target)


def test_dotted_group_on_primary_collection(template):
    template["operations"]["group"]["by"] = "details.region"
    assert translate_mongodb(template, database="travel").pipeline[0]["$group"]["_id"] == {
        "details_region": "$details.region"
    }
    statement = translate_couchbase(template, bucket="travel").statement
    assert "`bookings`.`details`.`region` AS `details_region`" in statement
    assert statement.endswith("GROUP BY `bookings`.`details`.`region`;")


Q7 = json.loads((Path(__file__).parent / "fixtures" / "q7_translation.json").read_text())


def test_q7_matches_corrected_jsonbench():
    template = copy.deepcopy(Q7["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q7["mongodb_pipeline"]
    assert mongo.collection == MongoCollectionRef("travel", "tours")
    assert couch.statement == Q7["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert template == Q7["template"]
    assert MongoAggregateQuery.from_json(mongo.to_json()) == mongo
    assert CouchbaseQuery.from_json(couch.to_json()) == couch


Q8 = json.loads((Path(__file__).parent / "fixtures" / "q8_translation.json").read_text())


def test_q8_matches_corrected_jsonbench():
    template = copy.deepcopy(Q8["template"])
    mongo = translate_mongodb(template, database="travel")
    couch = translate_couchbase(template, bucket="travel")
    assert mongo.pipeline == Q8["mongodb_pipeline"]
    assert couch.statement == Q8["couchbase_statement"]
    assert couch.query_context == "default:`travel`.`_default`"
    assert template == Q8["template"]


def test_joined_unnest_short_path():
    template = copy.deepcopy(Q8["template"])
    template["operations"]["unnest"][0]["field"] = "travellers"
    before = copy.deepcopy(template)
    assert translate_mongodb(template, database="travel").pipeline == Q8["mongodb_pipeline"]
    assert translate_couchbase(template, bucket="travel").statement == Q8["couchbase_statement"]
    assert template == before


@pytest.mark.parametrize("by", [[], ["a.b", "a_b"], ["destination", "destination"], [None]])
def test_invalid_composite_groups(by):
    template = copy.deepcopy(Q8["template"])
    template["operations"]["group"]["by"] = by
    for translate, target in [
        (translate_mongodb, {"database": "travel"}),
        (translate_couchbase, {"bucket": "travel"}),
    ]:
        with pytest.raises(ValueError):
            translate(template, **target)


def test_single_element_group_list_preserves_object_key(template):
    template["operations"]["group"]["by"] = ["tour_id"]
    assert translate_mongodb(template, database="travel").pipeline[0]["$group"]["_id"] == {
        "tour_id": "$tour_id"
    }


def test_composite_group_aggregate_collision():
    template = copy.deepcopy(Q8["template"])
    template["operations"]["group"]["aggregates"] = {"bookings_travellers_nationality": "count(*)"}
    with pytest.raises(ValueError, match="collide"):
        translate_couchbase(template, bucket="travel")
