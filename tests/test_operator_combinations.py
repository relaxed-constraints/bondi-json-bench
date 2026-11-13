"""Reference-output and rejection coverage beyond the eight paper queries."""

import copy
import json
from pathlib import Path

import pytest
from template_cases import generated_templates

from json_bench.queries import translate_couchbase, translate_mongodb

REFERENCE = json.loads((Path(__file__).parent / "fixtures/operator_combinations.json").read_text())


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_reference_output(case):
    template = copy.deepcopy(case["template"])
    mongo = translate_mongodb(template, database="travel")
    assert mongo.pipeline == case["mongodb_pipeline"]
    assert translate_couchbase(template, bucket="travel").statement == case["couchbase_statement"]
    assert template == case["template"]


def test_seeded_cases_match_capture():
    assert list(generated_templates()) == [c["template"] for c in REFERENCE["cases"][7:]]


@pytest.mark.parametrize(
    "ops",
    [
        {"project": {}},
        {"project": {"name": 0}},
        {"project": {"name": True}},
        {"group": {"by": "name", "aggregates": {}}, "project": {"name": 1}},
        {"sort": {"field": "name", "direction": True}},
        {"sort": {"field": "name", "direction": 0}},
        {"project": {"name": 1}, "sort": {"field": "score", "direction": 1}},
        {"group": {"by": "name", "aggregates": {}}, "sort": {"field": "name", "direction": 1}},
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"limit": 1.5},
    ],
)
def test_rejected_combinations(ops):
    template = {"primary_collection": "tours", "operations": ops}
    for translate, target in [
        (translate_mongodb, {"database": "travel"}),
        (translate_couchbase, {"bucket": "travel"}),
    ]:
        with pytest.raises(ValueError):
            translate(template, **target)
