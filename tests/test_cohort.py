"""Cohort weighting and plots with variable dimensions and missing cells."""

import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from json_bench.analysis import prepare_cohort
from json_bench.plotting import (
    plot_cohort_query_outcomes,
    plot_cohort_query_runtimes,
    plot_failure_heatmaps,
    plot_outcome_percentages,
)


def cohort():
    runs = pd.DataFrame(
        [
            {"backend": "mongodb", "clients": 3, "scale_factor": 0.5},
            {"backend": "mongodb", "clients": 3, "scale_factor": 0.5},
            {"backend": "couchbase", "clients": 7, "scale_factor": 2},
        ],
        index=["a", "b", "c"],
    )
    summaries, queries = {}, {}
    for run, successes, errors in [("a", 9, 0), ("b", 0, 1), ("c", 2, 0)]:
        counts = dict(
            success_count=successes, error_count=errors, timeout_count=0, unresolved_count=0
        )
        summaries[run] = dict(
            **counts, measurement_admissions=successes + errors, early_terminated=False
        )
        queries[run] = [
            dict(
                **counts,
                label="Q1",
                workload_position=0,
                successful_runtime_seconds=[1.0] * successes,
            )
        ]
    return prepare_cohort(runs, summaries, queries)


def test_repetition_percentages_are_not_pooled():
    data = cohort()
    fig = plot_failure_heatmaps(data)
    grid = fig.axes[0].images[0].get_array()
    assert grid[0, 0] == 50  # Equal run weighting; pooled failure rate would be 10%.
    assert np.ma.is_masked(grid[0, 1])
    assert [t.get_text() for t in fig.axes[0].get_yticklabels()] == ["0.5", "2.0"]
    assert [t.get_text() for t in fig.axes[1].get_xticklabels()] == ["3", "7"]


def test_all_cohort_charts_render_variable_dimensions():
    data = cohort()
    boxes = plot_cohort_query_runtimes(data)
    counts = plot_cohort_query_outcomes(data)
    assert set(boxes) == {0.5, 2, None}
    assert set(counts) == {0.5, 2, None}
    # All-scale counts sum all runs, not means or normalized percentages.
    assert sum(p.get_height() for p in counts[None].axes[0].patches) == 12
    for fig in [
        plot_outcome_percentages(data),
        plot_failure_heatmaps(data),
        *boxes.values(),
        *counts.values(),
    ]:
        FigureCanvasAgg(fig).draw()
        assert fig.dpi == 200


def test_empty_cohort_is_rejected():
    with pytest.raises(ValueError, match="nonempty"):
        prepare_cohort(pd.DataFrame(), {}, {})
