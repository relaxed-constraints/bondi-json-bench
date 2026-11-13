"""Check plotted populations, outcome stacks, labels and standalone rendering."""

from dataclasses import replace

import matplotlib as mpl
import pytest
from bondi.execution import ExecutionResult
from bondi.load import LoadResult
from matplotlib.backends.backend_agg import FigureCanvasAgg

from json_bench.analysis import analyse_load_results
from json_bench.plotting import plot_query_outcomes, plot_query_runtimes


def analysis():
    rows = [
        LoadResult(i, 0, i, 0, "measurement", 5 + i, 6 + i, True, ExecutionResult(value))
        for i, value in enumerate([1000, 2000, 3000])
    ]
    rows.extend(
        [
            LoadResult(
                3, 0, 3, 0, "measurement", 8, 9, True, ExecutionResult(1, error=RuntimeError())
            ),
            LoadResult(
                4, 0, 4, 0, "measurement", 9, 10, True, ExecutionResult(1, error=TimeoutError())
            ),
            LoadResult(5, 0, 5, 0, "measurement", 10, 35, True, None, "drain_timeout"),
        ]
    )
    return analyse_load_results(
        rows, query_labels=["Q1", "Q2"], warmup_seconds=5, measurement_seconds=15
    )


def test_runtime_boxes_and_no_success_label(tmp_path):
    prepared = analysis()
    original_font = mpl.rcParams["font.size"]
    fig = plot_query_runtimes({"MongoDB": prepared, "Couchbase": prepared})
    ax = fig.axes[0]
    assert fig.dpi == 200
    assert ax.get_yscale() == "log"
    assert len(ax.patches) == 2
    assert sum(t.get_text() == "No successes" for t in ax.texts) == 2
    assert any(
        list(line.get_ydata()) == [2, 2] for line in ax.lines
    )  # Median of sample population.
    assert [t.get_text() for t in ax.get_xticklabels()] == ["Q1", "Q2"]
    FigureCanvasAgg(fig).draw()
    fig.savefig(tmp_path / "runtime.png")
    assert (tmp_path / "runtime.png").stat().st_size > 1000
    assert mpl.rcParams["font.size"] == original_font


def test_outcome_stack_counts_and_two_legend_rows(tmp_path):
    prepared = analysis()
    fig = plot_query_outcomes({"MongoDB": prepared, "Couchbase": prepared})
    ax = fig.axes[0]
    assert [patch.get_height() for patch in ax.patches[:8]] == [3, 0, 1, 0, 1, 0, 1, 0]
    assert sum(patch.get_height() for patch in ax.patches) == 12
    assert [text.get_text() for text in ax.artists[0].get_texts()] == [
        "Success",
        "Error",
        "Timeout",
        "Unresolved",
    ]
    assert [text.get_text() for text in ax.get_legend().get_texts()] == ["MongoDB", "Couchbase"]
    FigureCanvasAgg(fig).draw()
    fig.savefig(tmp_path / "outcomes.png")


@pytest.mark.parametrize("plot", [plot_query_runtimes, plot_query_outcomes])
def test_alignment_empty_and_options(plot):
    prepared = analysis()
    with pytest.raises(ValueError):
        plot({})
    changed = replace(
        prepared, queries=(replace(prepared.queries[0], label="Different"), prepared.queries[1])
    )
    with pytest.raises(ValueError, match="matching"):
        plot({"A": prepared, "B": changed})
    with pytest.raises(ValueError, match="figsize"):
        plot({"A": prepared}, figsize=(0, 4))
    empty = analyse_load_results([], query_labels=["Q1"], warmup_seconds=0, measurement_seconds=1)
    FigureCanvasAgg(plot({"A": empty})).draw()


def test_zero_runtime_and_early_stop_are_visible():
    prepared = analysis()
    zero = replace(
        prepared,
        summary=replace(prepared.summary, early_terminated=True),
        queries=(replace(prepared.queries[0], successful_runtime_seconds=(0.0,)),),
    )
    with pytest.raises(ValueError, match="positive"):
        plot_query_runtimes({"A": zero})
    fig = plot_query_runtimes({"A": zero}, log_scale=False)
    assert "early stop" in fig.axes[0].get_legend().get_texts()[0].get_text()
    with pytest.raises(ValueError, match="Whisker"):
        plot_query_runtimes({"A": prepared}, whisker_percentiles=(40, 60))
