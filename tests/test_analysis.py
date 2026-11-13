"""Measurement boundaries and outcomes for sustained-load summaries."""

import pytest
from bondi.execution import ExecutionResult
from bondi.load import LoadResult

from json_bench.analysis import summarise_load_results


def observation(i, start, end, elapsed=1000, error=None, reason=None):
    result = None if reason == "drain_timeout" else ExecutionResult(elapsed, error=error)
    return LoadResult(
        i, 0, i, 0, "warmup" if start < 5 else "measurement", start, end, True, result, reason
    )


def summary(rows):
    return summarise_load_results(rows, warmup_seconds=5, measurement_seconds=15)


def test_warmup_draining_and_all_outcomes():
    rows = [
        observation(0, 4, 6, 90000),
        observation(1, 5, 6, 100),
        observation(2, 19, 20, 300),
        observation(3, 19.5, 23, 2000),
        observation(4, 8, 9, error=RuntimeError()),
        observation(5, 9, 22, error=TimeoutError()),
        observation(6, 19, 35, reason="drain_timeout"),
    ]
    result = summary(rows)
    assert result.measurement_admissions == 6
    assert result.successes_within_window == 1
    assert result.throughput_queries_per_second == pytest.approx(1 / 15)
    assert result.success_count == 3
    assert result.error_count == result.timeout_count == result.unresolved_count == 1
    assert result.mean_runtime_seconds == pytest.approx(0.8)
    assert result.median_runtime_seconds == 0.3
    assert not result.early_terminated
    assert result.stop_reasons == ("drain_timeout",)


def test_empty_and_no_success():
    for rows in [[], [observation(0, 5, 6, error=TimeoutError())]]:
        result = summary(rows)
        assert result.mean_runtime_seconds is result.median_runtime_seconds is None
        assert result.throughput_queries_per_second == 0


@pytest.mark.parametrize("reason", ["query_error", "database_unavailable"])
def test_early_stop_in_warmup(reason):
    result = summary([observation(0, 1, 2, error=RuntimeError(), reason=reason)])
    assert result.early_terminated
    assert result.measurement_admissions == 0
    assert result.measurement_seconds == 15


def test_order_independent_and_does_not_mutate():
    rows = [observation(0, 5, 7), observation(1, 8, 9)]
    assert summary(rows) == summary(list(reversed(rows)))
    assert rows[0].ended_seconds == 7


@pytest.mark.parametrize(
    "warmup,measurement",
    [(-1, 1), (0, 0), (0, -1), (float("nan"), 1), (0, float("inf")), (True, 1)],
)
def test_bad_windows(warmup, measurement):
    with pytest.raises(ValueError):
        summarise_load_results([], warmup_seconds=warmup, measurement_seconds=measurement)


def test_duplicate_ids_and_bad_timestamps():
    row = observation(0, 5, 6)
    with pytest.raises(ValueError, match="Duplicate"):
        summary([row, row])
    for row in [observation(0, 20, 21), observation(0, 7, 6), observation(0, 5, 6, -1)]:
        with pytest.raises(ValueError):
            summary([row])


def test_query_analysis_reconciles_with_run_and_keeps_empty_queries():
    from dataclasses import replace

    from json_bench.analysis import analyse_load_results

    rows = [
        observation(0, 4, 6, 90000, reason="query_error", error=RuntimeError()),
        observation(1, 5, 6, 100),
        observation(2, 19, 20, 300),
        replace(observation(3, 19.5, 23, 2000), workload_position=1),
        replace(observation(4, 8, 9, error=RuntimeError()), workload_position=1),
        replace(observation(5, 9, 22, error=TimeoutError()), workload_position=1),
        replace(observation(6, 19, 35, reason="drain_timeout"), workload_position=1),
    ]
    analysis = analyse_load_results(
        rows, query_labels=["Q1", "Q2", "Q3"], warmup_seconds=5, measurement_seconds=15
    )
    assert analysis.summary == summary(rows)
    assert analysis.summary.early_terminated
    assert analysis.queries[0].successful_runtime_seconds == (0.1, 0.3)
    assert analysis.queries[1].successful_runtime_seconds == (2.0,)
    assert analysis.queries[2].successful_runtime_seconds == ()
    assert analysis.queries[2].mean_runtime_seconds is None
    assert analysis.queries[2].measurement_admissions == 0
    assert [q.label for q in analysis.queries] == ["Q1", "Q2", "Q3"]
    for field in [
        "measurement_admissions",
        "successes_within_window",
        "success_count",
        "error_count",
        "timeout_count",
        "unresolved_count",
    ]:
        assert sum(getattr(q, field) for q in analysis.queries) == getattr(analysis.summary, field)
    assert analysis.summary.mean_runtime_seconds == pytest.approx(0.8)  # Pooled, not query means.


@pytest.mark.parametrize("labels", [[], "Q1", [""], [None], ["Q1", "Q1"]])
def test_invalid_query_labels(labels):
    from json_bench.analysis import analyse_load_results

    with pytest.raises(ValueError, match="query_labels"):
        analyse_load_results([], query_labels=labels, warmup_seconds=5, measurement_seconds=15)


@pytest.mark.parametrize("position", [-1, 1, True, 0.5])
def test_invalid_workload_position_even_during_warmup(position):
    from dataclasses import replace

    from json_bench.analysis import analyse_load_results

    row = replace(observation(0, 1, 2), workload_position=position)
    with pytest.raises(ValueError, match="workload_position"):
        analyse_load_results([row], query_labels=["Q1"], warmup_seconds=5, measurement_seconds=15)


def test_query_analysis_empty_and_input_unchanged():
    import copy

    from json_bench.analysis import analyse_load_results

    rows = [observation(0, 5, 6)]
    before = copy.deepcopy(rows)
    analyse_load_results(rows, query_labels=["Q1"], warmup_seconds=5, measurement_seconds=15)
    assert rows == before
    empty = analyse_load_results([], query_labels=["Q1"], warmup_seconds=5, measurement_seconds=15)
    assert empty.summary == summary([])
    assert empty.queries[0].success_count == 0
