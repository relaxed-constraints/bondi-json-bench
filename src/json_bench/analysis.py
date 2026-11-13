"""Pure metric calculations for one BONDI sustained-load run."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, median

from bondi.load import LoadResult


@dataclass(frozen=True)
class LoadSummary:
    """Metrics for measurement admissions, with warm-up excluded.

    Throughput counts successful admissions completed inside the measurement
    window. Runtimes and outcome counts also include drain completions.
    Runtime values are seconds from ExecutionResult.elapsed_ms, not LoadResult.duration.
    early_terminated reports observed admission-stop reasons, not proof that an
    arbitrary input list contains every observation. Drain expiry is separate.
    """

    measurement_seconds: float
    measurement_admissions: int
    successes_within_window: int
    throughput_queries_per_second: float
    mean_runtime_seconds: float | None
    median_runtime_seconds: float | None
    success_count: int
    error_count: int
    timeout_count: int
    unresolved_count: int
    early_terminated: bool
    stop_reasons: tuple[str, ...]


@dataclass(frozen=True)
class QuerySummary:
    """Measurement outcomes and successful runtime samples for one workload entry.

    Queries with no measurement admissions have zero counts, None means/medians,
    and an empty sample tuple. Early termination belongs to the whole run.
    """

    workload_position: int
    label: str
    measurement_admissions: int
    successes_within_window: int
    mean_runtime_seconds: float | None
    median_runtime_seconds: float | None
    success_count: int
    error_count: int
    timeout_count: int
    unresolved_count: int
    successful_runtime_seconds: tuple[float, ...]


@dataclass(frozen=True)
class LoadAnalysis:
    """One run's summary and workload-ordered query summaries; never pooled runs."""

    summary: LoadSummary
    queries: tuple[QuerySummary, ...]


def summarise_load_results(
    results: Sequence[LoadResult],
    *,
    warmup_seconds: float,
    measurement_seconds: float,
) -> LoadSummary:
    """Summarise one complete retained generate_load() result list.

    Args:
        results: All observations from one run, including warm-up. Do not combine
            repetitions or omit failures. Admission IDs must be unique.
        warmup_seconds: Configured nonnegative warm-up duration.
        measurement_seconds: Configured positive measurement duration.

    Returns:
        LoadSummary with fixed-window throughput, successful-query runtimes and
        mutually exclusive outcome counts. Empty runtime samples yield None.
        Early-stop reasons from warm-up also flag early_terminated. The planned
        denominator is never shortened; flagged runs are not normal full runs.

    Raises:
        ValueError: Invalid durations, duplicate IDs or inconsistent observations.

    Measurement is the half-open interval [warmup, warmup + measurement).
    Warm-up admissions are excluded even if they finish inside that interval.
    Drain-expired observations remain unresolved, not database timeouts.
    No observation list can prove that a caller retained every result or that an
    empty run completed normally; early_terminated only reports explicit evidence.
    """
    measurement, reasons = _prepare_results(results, warmup_seconds, measurement_seconds)
    return _run_summary(measurement, reasons, warmup_seconds, measurement_seconds)


def _prepare_results(results, warmup_seconds, measurement_seconds):
    """Validate one run and select measurement admissions, including drain finishes."""
    for label, value in [
        ("warmup_seconds", warmup_seconds),
        ("measurement_seconds", measurement_seconds),
    ]:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{label} must be finite and nonnegative")
    if measurement_seconds == 0:
        raise ValueError("measurement_seconds must be positive")
    end = warmup_seconds + measurement_seconds
    if not math.isfinite(end):
        raise ValueError("Measurement end must be finite")
    seen = set()
    reasons = set()
    measurement = []
    for observation in results:
        if observation.attempt_id in seen:
            raise ValueError("Duplicate attempt_id; supply observations from one run")
        seen.add(observation.attempt_id)
        admitted, ended = observation.admitted_seconds, observation.ended_seconds
        if (
            not (math.isfinite(admitted) and math.isfinite(ended))
            or admitted < 0
            or ended < admitted
        ):
            raise ValueError("Observation timestamps must be finite, nonnegative and ordered")
        expected_phase = "warmup" if admitted < warmup_seconds else "measurement"
        if observation.phase_started != expected_phase or admitted >= end:
            raise ValueError("Observation admission does not match the configured phases")
        if observation.stop_reason:
            reasons.add(observation.stop_reason)
        if observation.phase_started == "warmup":
            continue
        if observation.result is not None and observation.result.status == "success":
            runtime = observation.result.elapsed_ms / 1000
            if not math.isfinite(runtime) or runtime < 0:
                raise ValueError("Successful query runtime must be finite and nonnegative")
        measurement.append(observation)
    return measurement, reasons


def _metrics(measurement, end):
    """Count outcomes and extract successful runtimes using one shared policy."""
    counts = dict(success=0, error=0, timeout=0, unresolved=0)
    runtimes = []
    within = 0
    for observation in measurement:
        if observation.result is None:
            counts["unresolved"] += 1
            continue
        outcome = observation.result.status
        counts[outcome] += 1
        if outcome == "success":
            runtimes.append(observation.result.elapsed_ms / 1000)
            if observation.ended_seconds < end:
                within += 1
    return dict(
        measurement_admissions=sum(counts.values()),
        successes_within_window=within,
        mean_runtime_seconds=mean(runtimes) if runtimes else None,
        median_runtime_seconds=median(runtimes) if runtimes else None,
        success_count=counts["success"],
        error_count=counts["error"],
        timeout_count=counts["timeout"],
        unresolved_count=counts["unresolved"],
    ), tuple(runtimes)


def _run_summary(measurement, reasons, warmup_seconds, measurement_seconds):
    """Build the existing run summary from validated observations."""
    metrics, _ = _metrics(measurement, warmup_seconds + measurement_seconds)
    return LoadSummary(
        **metrics,
        measurement_seconds=measurement_seconds,
        throughput_queries_per_second=metrics["successes_within_window"] / measurement_seconds,
        early_terminated=bool(reasons & {"query_error", "database_unavailable"}),
        stop_reasons=tuple(sorted(reasons)),
    )


def analyse_load_results(
    results: Sequence[LoadResult],
    *,
    query_labels: Sequence[str],
    warmup_seconds: float,
    measurement_seconds: float,
) -> LoadAnalysis:
    """Prepare one run and its per-query samples for tables and plots.

    Args:
        results: Complete retained observations from one generate_load call.
        query_labels: Nonempty unique labels in workload order, including queries
            with no attempts. For example, ["Q1", "Q2"].
        warmup_seconds: Configured warm-up duration.
        measurement_seconds: Configured measurement duration.

    Returns:
        LoadAnalysis with the same summary as summarise_load_results and one
        QuerySummary per workload entry. Samples contain successful measurement
        admissions, including drain completions, in supplied observation order.
        Runtime is ExecutionResult.elapsed_ms / 1000. Inputs are not modified.

    Raises:
        ValueError: Invalid labels, out-of-range workload positions or invalid
            observations/windows as described by summarise_load_results.

    No repetitions or configurations are pooled. Per-query outcome counts and
    in-window successes sum to run totals. Run means use all successful attempts,
    not an unweighted average of query means. Stop reasons remain run-level.
    """
    labels = tuple(query_labels)
    if (
        isinstance(query_labels, str)
        or not labels
        or any(not isinstance(label, str) or not label.strip() for label in labels)
    ):
        raise ValueError("query_labels must be a nonempty sequence of nonblank strings")
    if len(set(labels)) != len(labels):
        raise ValueError("query_labels must be unique")
    for item in results:
        if type(item.workload_position) is not int or not 0 <= item.workload_position < len(labels):
            raise ValueError("workload_position is outside query_labels")
    measurement, reasons = _prepare_results(results, warmup_seconds, measurement_seconds)
    buckets = [[] for _ in labels]
    for item in measurement:
        buckets[item.workload_position].append(item)
    queries = []
    for position, (label, bucket) in enumerate(zip(labels, buckets, strict=True)):
        metrics, samples = _metrics(bucket, warmup_seconds + measurement_seconds)
        queries.append(
            QuerySummary(
                workload_position=position,
                label=label,
                **metrics,
                successful_runtime_seconds=samples,
            )
        )
    return LoadAnalysis(
        summary=_run_summary(measurement, reasons, warmup_seconds, measurement_seconds),
        queries=tuple(queries),
    )
