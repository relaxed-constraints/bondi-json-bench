"""Grouped-result comparison checks independent of a live database."""

import copy

import pytest
from bondi.execution import ExecutionResult

from json_bench.validate import compare_results

TEMPLATE = {
    "name": "Example",
    "operations": {"group": {"by": "tour_id", "aggregates": {"value": "sum(price)"}}},
}


def result(rows):
    return ExecutionResult(elapsed_ms=1, documents=rows)


def test_order_rounding_and_no_mutation():
    mongo = result([{"_id": "a", "value": 10}, {"_id": "b", "value": 20}])
    couch = result([{"tour_id": "b", "value": 20.0}, {"tour_id": "a", "value": 10.00000001}])
    before = copy.deepcopy((TEMPLATE, mongo, couch))
    compare_results(TEMPLATE, mongo, couch)
    assert (TEMPLATE, mongo, couch) == before


@pytest.mark.parametrize(
    "by,key,couch_key",
    [
        ("joined.key", {"joined_key": "a"}, {"joined_key": "a"}),
        (["tour_id"], {"tour_id": "a"}, {"tour_id": "a"}),
        (
            ["destination", "traveller.nation"],
            {"destination": "x", "traveller_nation": "AU"},
            {"destination": "x", "traveller_nation": "AU"},
        ),
    ],
)
def test_group_shapes(by, key, couch_key):
    template = copy.deepcopy(TEMPLATE)
    template["operations"]["group"]["by"] = by
    compare_results(
        template, result([{"_id": key, "value": 3}]), result([{**couch_key, "value": 3}])
    )


def test_empty_results():
    compare_results(TEMPLATE, result([]), result([]))


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"tour_id": "b", "value": 1}],
        [{"tour_id": "a", "value": 2}],
        [{"tour_id": "a"}],
        [{"tour_id": "a", "value": 1, "extra": 2}],
        [{"tour_id": "a", "value": 1}, {"tour_id": "a", "value": 1}],
    ],
)
def test_mismatch(rows):
    with pytest.raises(AssertionError, match="Example"):
        compare_results(TEMPLATE, result([{"_id": "a", "value": 1}]), result(rows))


def test_duplicate_mongo_groups():
    with pytest.raises(AssertionError, match="duplicate"):
        compare_results(TEMPLATE, result([{"_id": "a", "value": 1}] * 2), result([]))


def test_sort_order_is_checked():
    template = copy.deepcopy(TEMPLATE)
    template["operations"]["sort"] = {"field": "value", "direction": 1}
    with pytest.raises(AssertionError, match="ordered"):
        compare_results(
            template,
            result([{"_id": "a", "value": 1}, {"_id": "b", "value": 2}]),
            result([{"tour_id": "b", "value": 2}, {"tour_id": "a", "value": 1}]),
        )


@pytest.mark.parametrize(
    "bad", [None, ExecutionResult(1), ExecutionResult(1, error=RuntimeError("failed"))]
)
def test_execution_preconditions(bad):
    with pytest.raises(AssertionError):
        compare_results(TEMPLATE, bad, result([]))
    with pytest.raises(AssertionError):
        compare_results(TEMPLATE, result([]), bad)


def test_scope_and_tolerance_validation():
    with pytest.raises(ValueError, match="grouped"):
        compare_results({"operations": {}}, result([]), result([]))
    for value in [-1, float("nan"), float("inf")]:
        with pytest.raises(ValueError, match="rel_tol"):
            compare_results(TEMPLATE, result([]), result([]), rel_tol=value)


def test_null_and_type_differences():
    compare_results(
        TEMPLATE, result([{"_id": "a", "value": None}]), result([{"tour_id": "a", "value": None}])
    )
    with pytest.raises(AssertionError):
        compare_results(
            TEMPLATE, result([{"_id": "a", "value": 1}]), result([{"tour_id": "a", "value": True}])
        )
