# Reading the figures

The CLI and analysis notebook call the same plotting functions. Figures use
200 DPI by default. MongoDB is blue and Couchbase is orange in runtime and
throughput charts. Scale factors and client counts come from the selected runs.

## Throughput and mean runtime

`plot_client_scaling()` creates one column per scale factor. The top row shows
throughput; the bottom row shows mean successful query runtime. Lines show means
across repetitions. Shading spans the minimum and maximum repetition values,
not a standard deviation or confidence interval.

Successful runtime includes drain completions. Throughput counts only successful
measurement admissions completed inside the measurement window. See the
[metric definitions](analysis.md) for the exact rules.

## Outcome percentages and heatmaps

`plot_outcome_percentages()` shows success, error, timeout, and unresolved shares.
Percentages are averaged per run; they are not calculated from pooled counts.

`plot_failure_heatmaps()` shows the mean error-plus-timeout percentage. Unresolved
attempts remain in the denominator but are not counted as errors or timeouts.
Missing combinations have no value; they are not treated as zero failures.

## Per-query distributions

`plot_cohort_query_runtimes()` produces separate figures for each scale factor,
plus one for all scale factors. It pools successful runtime samples across client
counts and repetitions. Boxes show quartiles and the median. Whiskers use the
5th and 95th percentiles. Outlier markers are hidden, but samples are retained.

`plot_cohort_query_outcomes()` uses the same grouping and pools absolute outcome
counts. It does not normalize the bars. Colors identify outcomes and hatches
identify databases. Use counts to understand how much evidence each query has.

## Use the functions from Python

All plotting functions return Matplotlib figures without displaying or saving
them. For example:

```python
from json_bench.plotting import plot_client_scaling

figure = plot_client_scaling(cohort.runs)
figure.savefig("clients_by_scale.png", dpi=200, bbox_inches="tight")
```

`plot_query_runtimes()` and `plot_query_outcomes()` compare aligned single-run
`LoadAnalysis` objects. They do not pool configurations. Their labels mark
observed early termination. Runtime plots reject nonpositive samples on a log
axis; use `log_scale=False` when needed.

See the [plotting API](reference/plotting.md), or use
[`json-bench plot`](reference/cli/plot.md) to export the whole figure set.
