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
