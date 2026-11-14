# Execution and metrics

BONDI generates sustained load with one query in flight per client. Clients select
queries at random with the configured weights and submit another after completion.
The benchmark runs warm-up, measurement, and draining in that order.

## Measurement window

Let `W` be warm-up duration and `M` measurement duration. A query belongs to the
measurement sample if it starts in `[W, W + M)`. Queries started during warm-up
are excluded, even if they finish during measurement. No new queries are admitted
after measurement; draining gives in-flight queries time to finish.

| Metric | Definition |
| --- | --- |
| Throughput | Successful measurement admissions completed before `W + M`, divided by `M` |
| Mean runtime | Mean execution time of successful measurement admissions, including drain completions |
| Median runtime | Median of those same successful execution times |
| Success, error, timeout counts | Final outcomes of measurement admissions, including draining |
| Unresolved count | Measurement admissions with no execution result, including drain expiry |

Runtime is BONDI's `ExecutionResult.elapsed_ms / 1000`. It excludes the health
preflight and differs from `LoadResult.duration`, which includes that preflight.
Errors, timeouts, and unresolved attempts do not enter runtime statistics.


## Early termination

A `query_error` or `database_unavailable` stop reason flags early termination,
even if it occurs during warm-up. The throughput denominator remains the configured
measurement duration. The runner saves partial evidence, then reports failure.
Cohort analysis rejects early-stopped summaries.

## Per-query summaries

`analyse_load_results()` returns a run summary and one summary per workload entry.
Labels remain present even when a query has no admissions. Per-query counts sum
to the run counts. Run runtime statistics use all successful samples, not an
average of per-query means or medians.

```python
from json_bench.analysis import analyse_load_results

analysis = analyse_load_results(
    results,
    query_labels=[f"Q{i}" for i in range(1, 9)],
    warmup_seconds=60,
    measurement_seconds=180,
)
print(analysis.summary.throughput_queries_per_second)
```
See the [analysis API](reference/analysis.md) for all fields and functions.

## Repetitions and cohorts

`prepare_cohort()` combines saved run summaries and per-query artifacts with
backend, client count, and scale-factor metadata. It checks outcome totals,
query labels, and successful sample counts. The caller must select compatible
workloads and execution settings.

Scaling charts give each repetition equal weight. Their shading spans the
minimum and maximum run values. Outcome percentages are averaged per run.
Per-query distributions and count charts pool samples and counts across the
selected runs. See [Reading the figures](plotting.md).

Always report outcomes alongside runtime. Timeouts can remove slow queries from
the successful sample and make the mean runtime appear lower.
