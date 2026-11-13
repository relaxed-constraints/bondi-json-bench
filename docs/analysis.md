# Summarise sustained load

```python
from json_bench.analysis import summarise_load_results

summary = summarise_load_results(
    load_results["mongodb"],
    warmup_seconds=5,
    measurement_seconds=15,
)
print(summary.throughput_queries_per_second)
```

## API

`summary = summarise_load_results(results, *, warmup_seconds,
measurement_seconds)` returns a frozen `LoadSummary` dataclass.
Supply the complete retained BONDI result list from one run, including warm-up
and failures. Duplicate attempt IDs are rejected. Do not combine repetitions.
The function does not access files, databases, pandas or plotting libraries.

Measurement is `[warmup_seconds, warmup_seconds + measurement_seconds)`.
Admissions at the start are included; admissions at the end are not valid.
Warm-up admissions are excluded even when they finish during measurement.

| Field | Definition |
|---|---|
| measurement_seconds | Configured measurement duration |
| measurement_admissions | All attempts admitted during measurement |
| successes_within_window | Measurement admissions that succeed before the window ends |
| throughput_queries_per_second | successes_within_window divided by measurement_seconds |
| mean_runtime_seconds, median_runtime_seconds | Successful measurement admissions, including drain completions |
| success_count, error_count, timeout_count | Final outcomes of measurement admissions, including draining |
| unresolved_count | Measurement admissions without an execution result |
| early_terminated | An explicit query_error or database_unavailable stop reason was observed |
| stop_reasons | Distinct stop reasons across all phases, including warm-up |

Runtime uses `ExecutionResult.elapsed_ms / 1000`, excluding health preflight.
It does not use `LoadResult.duration`, which includes that preflight. Failed,
timed-out and unresolved attempts are excluded from runtime statistics. No
successful samples yields None, not zero. Drain expiry remains unresolved.
The four outcome counts sum to measurement_admissions.

Early-stop evidence never shortens the throughput denominator. Treat flagged
runs separately from full-duration runs. Stop reasons from warm-up also flag the
run. Drain expiry alone does not mean admissions stopped early; inspect the
unresolved count separately.

The input list cannot prove that the caller retained every observation. In
particular, an empty list does not establish successful completion. The
`early_terminated` field reports explicit evidence, not a completeness guarantee.
No finite sample of successful runtimes describes timed-out query durations;
report failures alongside runtime metrics to avoid hiding that selection effect.

## Per-query analysis

```python
from json_bench.analysis import analyse_load_results

analysis = analyse_load_results(
    load_results["mongodb"],
    query_labels=[f"Q{i}" for i in range(1, 9)],
    warmup_seconds=WARMUP_SECONDS,
    measurement_seconds=MEASUREMENT_SECONDS,
)
print(analysis.summary.throughput_queries_per_second)
print(analysis.queries[0].median_runtime_seconds)
```

### API

```python
analyse_load_results(
    results: Sequence[LoadResult],
    *,
    query_labels: Sequence[str],
    warmup_seconds: float,
    measurement_seconds: float,
) -> LoadAnalysis
```

`LoadAnalysis` is a frozen dataclass with two fields:

- `summary`: the same `LoadSummary` returned by `summarise_load_results()`.
- `queries`: a tuple of `QuerySummary` objects in workload order.

`QuerySummary` contains `workload_position`, `label`, `measurement_admissions`,
`successes_within_window`, `success_count`, `error_count`, `timeout_count`,
`unresolved_count`, `mean_runtime_seconds`, `median_runtime_seconds`, and
`successful_runtime_seconds` (a tuple of samples).

Supply one unique, nonblank label per workload entry, including unused entries.
Out-of-range positions raise ValueError, including positions on warm-up records.
A query with no measurement admissions remains present with zero counts, None
means/medians and an empty sample tuple. A query with only failures also has no
successful runtime samples.

The same accounting code calculates run and query metrics. Per-query outcome
counts and in-window successes sum to their run totals. Run mean and median use
all successful samples; they are not averages of the per-query statistics.
Warm-up samples are excluded. Successful measurement admissions completed during
draining are included in runtime samples, but not in throughput.

Early termination and stop reasons remain run-level information. A failure from
one query can stop admissions for every query. Do not interpret an empty sample
as evidence that a query was fast or successful.

This API describes one run. It does not pool repetitions, scale factors or client
counts. Pandas can turn summaries into tables in the notebook or experiment code;
the analysis module itself has no pandas, plotting or database connection logic.
