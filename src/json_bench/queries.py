"""Translate the Q1 grouping subset into native BONDI query objects."""

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


def _group(template):
    """Validate the shared grouping subset and extract its parts.

    Return the primary collection, grouping field and an ordered mapping from
    output aliases to sum input fields. For example, total_revenue maps to
    total_price for sum(total_price). Both translators use this representation.

    The input template is only read, never changed. Unsupported structures raise
    ValueError. Incorrect template or expression types raise TypeError.
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dictionary")

    # Check the operation set before interpreting its contents.
    primary = _identifier(template.get("primary_collection"), "primary_collection")
    operations = template.get("operations")
    if not isinstance(operations, dict) or set(operations) != {"group"}:
        raise ValueError("Only the group operation is supported in this first version")

    # This first subset accepts one grouping field, not a list or dotted path.
    group = operations["group"]
    if not isinstance(group, dict) or set(group) != {"by", "aggregates"}:
        raise ValueError("group requires by and aggregates")

    by = _identifier(group["by"], "group.by")
    aggregates = group["aggregates"]
    if not isinstance(aggregates, dict) or not aggregates:
        raise ValueError("group.aggregates must be a nonempty dictionary")

    # Convert each expression into an output-name -> input-field mapping.
    sums = {}
    for alias, expr in aggregates.items():
        _identifier(alias, "Aggregate alias")
        if alias in {by, "_id"}:
            raise ValueError("Aggregate alias must not collide with the group field or _id")

        # Match the original parser's whitespace handling and case-insensitive sum.
        if not isinstance(expr, str):
            raise TypeError("Aggregate expression must be a string")

        match = re.fullmatch(r"(\w+)\((.*)\)", expr.strip())
        if not match or match[1].lower() != "sum":
            raise ValueError("Only sum(field) aggregates are supported")

        sums[alias] = _identifier(match[2].strip(), "Sum field")

    return primary, by, sums


def translate_mongodb(template: dict, *, database: str) -> MongoAggregateQuery:
    """Translate Q1-style grouping and sums into a MongoDB aggregation.

    Args:
        template: Original JSONBench template. Supports only group, one simple
            grouping field, and nonempty sum(field) aggregates.
        database: MongoDB database name, expressed as a simple identifier.

    Returns:
        A query targeting the template's primary_collection in database.

    Raises:
        TypeError: Incorrect template or expression type.
        ValueError: Unsupported operation, expression or identifier.

    Does not mutate the template, connect to a database, or create indexes.
    """
    _identifier(database, "database")
    primary, by, sums = _group(template)

    # MongoDB stores the grouping key in _id and uses $-prefixed field references.
    group_stage = {"_id": "$" + by}
    for alias, field in sums.items():
        group_stage[alias] = {"$sum": "$" + field}

    return MongoAggregateQuery(
        target=MongoCollectionRef(database, primary),
        pipeline=[{"$group": group_stage}],
    )


def translate_couchbase(template: dict, *, bucket: str, scope: str = "_default") -> CouchbaseQuery:
    """Translate Q1-style grouping and sums into a Couchbase SQL++ query.

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
    primary, by, sums = _group(template)

    # Qualify fields with the collection name and preserve the output aliases.
    fields = [f"`{primary}`.`{by}` AS `{by}`"]
    for alias, field in sums.items():
        fields.append(f"SUM(`{primary}`.`{field}`) AS `{alias}`")

    # Keep the original statement form. The context supplies its bucket and scope.
    return CouchbaseQuery(
        statement=f"SELECT {', '.join(fields)} FROM `{primary}` GROUP BY `{primary}`.`{by}`;",
        query_context=f"default:`{bucket}`.`{scope}`",
    )
