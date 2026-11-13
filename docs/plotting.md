# Plot query runtimes and outcomes

Prepare one analysis per backend, then pass those analyses to either plotting
function. Both functions return a Matplotlib Figure. They do not display figures,
save files or change global plotting settings.

```python
from IPython.display import display

from json_bench.analysis import analyse_load_results
from json_bench.plotting import plot_query_outcomes, plot_query_runtimes

analyses = {
    label: analyse_load_results(
        load_results[backend],
        query_labels=[f"Q{i}" for i in range(1, 9)],
        warmup_seconds=WARMUP_SECONDS,
        measurement_seconds=MEASUREMENT_SECONDS,
    )
    for backend, label in [("mongodb", "MongoDB"), ("couchbase", "Couchbase")]
}

runtime_figure = plot_query_runtimes(analyses)
outcome_figure = plot_query_outcomes(analyses)
display(runtime_figure)
display(outcome_figure)
# Optional: save an artifact from the notebook or Yanex experiment.
runtime_figure.savefig("query_runtimes.png", dpi=200, bbox_inches="tight")
```

## API

```python
plot_query_runtimes(
    analyses: Mapping[str, LoadAnalysis],
    *,
    log_scale: bool = True,
    whisker_percentiles: tuple[float, float] = (5, 95),
    figsize: tuple[float, float] = (10, 5),
    fontsize: float = 12,
    dpi: float = 200,
) -> Figure

plot_query_outcomes(
    analyses: Mapping[str, LoadAnalysis],
    *,
    figsize: tuple[float, float] = (10, 5),
    fontsize: float = 12,
    dpi: float = 200,
) -> Figure
```

The mapping keys are display labels. Its order determines backend order in the
charts and legends. Query positions and labels must match across all analyses;
otherwise the functions raise ValueError. Supply runs from the configuration you
want to compare. The functions cannot verify scale factors or client counts and
do not pool configurations or repetitions. Observed early-stopped runs are
labelled in the legends.

## Runtime distribution

The runtime chart uses separate boxes for each backend at each query. Boxes show
the 25th and 75th percentiles, with a black median line. Whiskers use the 5th and
95th percentile convention from the old JSONBench charts. Outlier markers are
hidden; their samples remain in the analysis statistics.

Only successful measurement admissions contribute samples, including successful
drain completions. The runtime unit is seconds. MongoDB is blue and Couchbase is
orange. Queries without successes show "No successes" instead of a box.

The default y-axis is logarithmic with ordinary numeric labels. Zero samples
cannot appear on a log axis: the function raises ValueError rather than silently
removing them. Use `log_scale=False` if zero runtimes are present. The whisker
percentiles must bracket the 25th and 75th percentiles.

## Outcome counts

The outcome chart has one stacked bar per backend per query. Colors identify
success, error, timeout and unresolved. Hatches identify backends. The legend
uses one row for outcome colors and a second row for backend hatches.

These are absolute attempt counts, not percentages or throughput. They include
all outcomes for measurement admissions, including draining. Warm-up admissions
are excluded. A zero-height bar means no measurement admissions for that query.
Use this chart alongside successful runtimes to see failure rates and sample
counts before drawing performance conclusions.
