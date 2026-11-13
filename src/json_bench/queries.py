"""Translate the Q1 and Q2 grouping subset into native BONDI query objects."""

import re

from bondi.couchbase import CouchbaseQuery
from bondi.mongodb import MongoAggregateQuery, MongoCollectionRef

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _identifier(value, label):
    """Validate a simple name and return it unchanged.

    Names can contain letters, digits and underscores, but cannot start with a
    digit. Dotted paths and query expressions are outside this initial subset.
    The label identifies the invalid input in the ValueError message.
    """
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a simple identifier")
    return value


def _path(value):
    """Validate each part of a dotted field path without treating it as SQL."""
    if not isinstance(value, str):
        raise ValueError("Field path must be a string")
    for part in value.split("."):
        _identifier(part, "Field path component")
    return value


def _unnests(operations, primary):
    """Read array paths in order. Only the primary collection is supported."""
    items = operations.get("unnest", [])
    if not isinstance(items, list):
        raise ValueError("unnest must be a list")

    paths = []
    for item in items:
        if isinstance(item, dict):
            if "field" not in item or set(item) - {"field", "from"}:
                raise ValueError("unnest requires field and an optional from")
            if item.get("from", primary) != primary:
                raise ValueError("unnest.from must name the primary collection")
            item = item["field"]
        paths.append(_path(item))
    return paths


def _group(template):
    """Validate the shared grouping subset and extract its parts.

    Return the primary collection, grouping field, aggregate expressions and array
    paths. Each expression is a (function, field) pair. Both translators use this
    representation.

    The input template is only read, never changed. Unsupported structures raise
    ValueError. Incorrect template or expression types raise TypeError.
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dictionary")

    # Check the operation set before interpreting its contents.
    primary = _identifier(template.get("primary_collection"), "primary_collection")
    operations = template.get("operations")
    if (
        not isinstance(operations, dict)
        or "group" not in operations
        or set(operations) - {"group", "unnest"}
    ):
        raise ValueError("Only group and optional unnest operations are supported")
    unnests = _unnests(operations, primary)

    # This first subset accepts one grouping field, not a list or dotted path.
    group = operations["group"]
    if not isinstance(group, dict) or set(group) != {"by", "aggregates"}:
        raise ValueError("group requires by and aggregates")

    by = _identifier(group["by"], "group.by")
    aggregates = group["aggregates"]
    if not isinstance(aggregates, dict) or not aggregates:
        raise ValueError("group.aggregates must be a nonempty dictionary")

    # Record each output name with its aggregate function and input path.
    expressions = {}
    for alias, expr in aggregates.items():
        _identifier(alias, "Aggregate alias")
        if alias in {by, "_id"}:
            raise ValueError("Aggregate alias must not collide with the group field or _id")

        # Match the original parser's whitespace handling and case-insensitive functions.
        if not isinstance(expr, str):
            raise TypeError("Aggregate expression must be a string")

        match = re.fullmatch(r"(\w+)\((.*)\)", expr.strip())
        if not match or match[1].lower() not in {"sum", "avg", "min", "max"}:
            raise ValueError("Supported aggregates are sum, avg, min and max over a field")

        expressions[alias] = (match[1].lower(), _path(match[2].strip()))

    return primary, by, expressions, unnests


def translate_mongodb(template: dict, *, database: str) -> MongoAggregateQuery:
    """Translate grouping, array expansion and aggregates into a MongoDB aggregation.

    Args:
        template: Original JSONBench template. Supports group and optional unnest, one simple
            grouping field, and sum/avg/min/max over field paths.
        database: MongoDB database name, expressed as a simple identifier.

    Returns:
        A query targeting the template's primary_collection in database.

    Raises:
        TypeError: Incorrect template or expression type.
        ValueError: Unsupported operation, expression or identifier.

    Does not mutate the template, connect to a database, or create indexes.
    """
    _identifier(database, "database")
    primary, by, expressions, unnests = _group(template)

    # MongoDB stores the grouping key in _id and uses $-prefixed field references.
    group_stage = {"_id": "$" + by}
    for alias, (function, field) in expressions.items():
        group_stage[alias] = {"$" + function: "$" + field}

    return MongoAggregateQuery(
        target=MongoCollectionRef(database, primary),
        pipeline=[{"$unwind": "$" + path} for path in unnests] + [{"$group": group_stage}],
    )


def translate_couchbase(template: dict, *, bucket: str, scope: str = "_default") -> CouchbaseQuery:
    """Translate grouping, array expansion and aggregates into a Couchbase SQL++ query.

    Args:
        template: Same supported template subset as translate_mongodb.
        bucket: Couchbase bucket name, expressed as a simple identifier.
        scope: Couchbase scope name, expressed as a simple identifier.

    Returns:
        The original JSONBench SQL++ form with an explicit bucket/scope context.

    Raises:
        TypeError: Incorrect template or expression type.
        ValueError: Unsupported operation, expression or identifier.

    Does not mutate the template, connect to a database, or create indexes.
    """
    _identifier(bucket, "bucket")
    _identifier(scope, "scope")
    primary, by, expressions, unnests = _group(template)

    # UNNEST changes how later field paths refer to the array elements.
    replacements = {}

    def quoted(path):
        """Quote each validated path component separately."""
        return ".".join(f"`{part}`" for part in path.split("."))

    def resolve(path):
        """Resolve array aliases before adding the primary collection name."""
        for original in sorted(replacements, key=len, reverse=True):
            if path == original or path.startswith(original + "."):
                return quoted(replacements[original] + path[len(original) :])
        if path.split(".")[0] == primary:
            return quoted(path)
        return quoted(primary + "." + path)

    clauses = []
    for index, path in enumerate(unnests):
        alias = f"__unnest_{index}"
        while alias == primary:
            alias += "_"
        clauses.append(f"UNNEST {resolve(path)} AS {quoted(alias)}")
        replacements[path] = alias

    fields = [f"{resolve(by)} AS {quoted(by)}"]
    for alias, (function, field) in expressions.items():
        fields.append(f"{function.upper()}({resolve(field)}) AS {quoted(alias)}")

    # Keep the original statement form. The context supplies its bucket and scope.
    parts = [f"SELECT {', '.join(fields)} FROM {quoted(primary)}", *clauses]
    parts.append(f"GROUP BY {resolve(by)}")
    return CouchbaseQuery(
        statement=" ".join(parts) + ";",
        query_context=f"default:`{bucket}`.`{scope}`",
    )
