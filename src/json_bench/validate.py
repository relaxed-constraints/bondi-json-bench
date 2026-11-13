"""Compare grouped MongoDB and Couchbase query results."""

import math
from numbers import Real

from bondi.execution import ExecutionResult


def compare_results(
    template: dict,
    mongo_result: ExecutionResult,
    couchbase_result: ExecutionResult,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-6,
) -> None:
    """Require equivalent collected results for a grouped template.

    Normalise MongoDB's _id and Couchbase's flat grouping aliases. Compare group
    keys exactly and numeric aggregates with the specified tolerances. Require
    unique groups; duplicate rows fail rather than disappearing during comparison.
    Sorted templates must return groups in the same order, including ties.
    Matching empty results are valid. Inputs are not modified.

    Args:
        template: Supported JSONBench template containing a group operation.
        mongo_result: Successful MongoDB execution with collected documents.
        couchbase_result: Successful Couchbase execution with collected documents.
        rel_tol: Nonnegative finite relative tolerance for numeric aggregates.
        abs_tol: Nonnegative finite absolute tolerance for numeric aggregates.

    Raises:
        ValueError: Ungrouped template or invalid tolerance.
        AssertionError: Failed/unstarted execution, missing documents, malformed
            rows, duplicate groups, or different keys, order, fields or values.

    Returns:
        None when the results match. Sort ties can differ legitimately between
        databases; use unique sort keys when checking ordered results.
    """
    for name, value in [("rel_tol", rel_tol), ("abs_tol", abs_tol)]:
        if not isinstance(value, Real) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    operations = template.get("operations", {})
    if "group" not in operations:
        raise ValueError("compare_results supports grouped templates only")
    group = operations["group"]
    by = group["by"]
    paths = by if isinstance(by, list) else [by]
    aliases = [path.replace(".", "_") for path in paths]
    aggregates = list(group["aggregates"])
    nested = isinstance(by, list) or "." in by
    label = template.get("name", "Query")

    def rows(result, backend):
        """Validate row shapes and retain every row for duplicate detection."""
        if result is None or result.error is not None:
            raise AssertionError(f"{label}: {backend} execution did not succeed")
        if result.documents is None:
            raise AssertionError(f"{label}: {backend} documents were not collected")
        normalised = []
        for index, row in enumerate(result.documents):
            fields = {"_id", *aggregates} if backend == "MongoDB" else {*aliases, *aggregates}
            if not isinstance(row, dict) or set(row) != fields:
                raise AssertionError(f"{label}: {backend} row {index} has unexpected fields")
            if backend == "MongoDB":
                key = row["_id"]
                if nested:
                    if not isinstance(key, dict) or set(key) != set(aliases):
                        raise AssertionError(
                            f"{label}: MongoDB row {index} has unexpected group keys"
                        )
                    key = tuple(key[alias] for alias in aliases)
                else:
                    key = (key,)
            else:
                key = tuple(row[alias] for alias in aliases)
            # Equality works for nested JSON values without assuming hashable keys.
            if any(key == previous for previous, _ in normalised):
                raise AssertionError(f"{label}: {backend} has duplicate group {key!r}")
            normalised.append((key, row))
        return normalised

    left = rows(mongo_result, "MongoDB")
    right = rows(couchbase_result, "Couchbase")
    if len(left) != len(right):
        raise AssertionError(f"{label}: group counts differ ({len(left)} vs {len(right)})")
    if "sort" in operations and [key for key, _ in left] != [key for key, _ in right]:
        raise AssertionError(f"{label}: ordered group keys differ")
    for key, mongo_row in left:
        matches = [row for other, row in right if other == key]
        if not matches:
            raise AssertionError(f"{label}: Couchbase is missing group {key!r}")
        couch_row = matches[0]
        for field in aggregates:
            a, b = mongo_row[field], couch_row[field]
            if (
                isinstance(a, Real)
                and isinstance(b, Real)
                and not isinstance(a, bool)
                and not isinstance(b, bool)
            ):
                equal = math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)
            else:
                equal = type(a) is type(b) and a == b
            if not equal:
                raise AssertionError(
                    f"{label}: group {key!r}, {field}: MongoDB {a!r} != Couchbase {b!r}"
                )
