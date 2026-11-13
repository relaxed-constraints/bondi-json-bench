"""Translate the Q1 grouping subset into native BONDI query objects."""

import re

from bondi.couchbase import CouchbaseQuery
from bondi.mongodb import MongoAggregateQuery, MongoCollectionRef

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def _identifier(value, label):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a simple identifier")
    return value


def _group(template):
    if not isinstance(template, dict):
        raise TypeError("template must be a dictionary")
    primary = _identifier(template.get("primary_collection"), "primary_collection")
    operations = template.get("operations")
    if not isinstance(operations, dict) or set(operations) != {"group"}:
        raise ValueError("Only the group operation is supported in this first version")
    group = operations["group"]
    if not isinstance(group, dict) or set(group) != {"by", "aggregates"}:
        raise ValueError("group requires by and aggregates")
    by = _identifier(group["by"], "group.by")
    aggregates = group["aggregates"]
    if not isinstance(aggregates, dict) or not aggregates:
        raise ValueError("group.aggregates must be a nonempty dictionary")
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
    return MongoAggregateQuery(
        target=MongoCollectionRef(database, primary),
        pipeline=[
            {
                "$group": {
                    "_id": "$" + by,
                    **{alias: {"$sum": "$" + field} for alias, field in sums.items()},
                }
            }
        ],
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
    fields = [f"`{primary}`.`{by}` AS `{by}`"]
    fields += [f"SUM(`{primary}`.`{field}`) AS `{alias}`" for alias, field in sums.items()]
    return CouchbaseQuery(
        statement=f"SELECT {', '.join(fields)} FROM `{primary}` GROUP BY `{primary}`.`{by}`;",
        query_context=f"default:`{bucket}`.`{scope}`",
    )
