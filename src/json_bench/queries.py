"""Translate the corrected JSONBench template subset into native BONDI query objects."""

import json
import math
import re
from pathlib import Path

from bondi.couchbase import CouchbaseQuery
from bondi.mongodb import MongoAggregateQuery, MongoCollectionRef

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def load_template(path: str | Path) -> dict:
    """Read one JSON template object from a UTF-8 file.

    Args:
        path: File path. Relative paths are resolved against the current directory.

    Returns:
        A fresh dictionary. This function does not validate query operations.
        Pass the dictionary to a translator to check supported syntax.

    Raises:
        OSError: The file cannot be opened or read.
        json.JSONDecodeError: The file does not contain valid JSON.
        ValueError: The JSON value is not an object.
    """
    template = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(template, dict):
        raise ValueError(f"Template file must contain a JSON object: {path}")
    return template


def _identifier(value, label):
    """Validate a simple name and return it unchanged.

    Names can contain letters, digits and underscores, but cannot start with a
    digit. Validate dotted field paths separately with _path.
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


def _joins(operations, primary):
    """Validate joins and copy them in template order.

    Each source becomes both a collection name and an alias. Reject duplicate
    sources and self joins because the template has no separate alias field.
    """
    items = operations.get("join", [])
    items = items if isinstance(items, list) else [items]
    sources = {primary}
    joins = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"from", "localField", "foreignField"}:
            raise ValueError("join requires from, localField and foreignField")
        source = _identifier(item["from"], "join.from")
        if source in sources:
            raise ValueError(
                "Join sources must be distinct from each other and the primary collection"
            )
        _path(item["localField"])
        _path(item["foreignField"])
        sources.add(source)
        joins.append(dict(item))
    return joins


def _unnests(operations, primary, joins):
    """Resolve array paths from the primary or a joined collection in order."""
    sources = {primary} | {join["from"] for join in joins}
    items = operations.get("unnest", [])
    if not isinstance(items, list):
        raise ValueError("unnest must be a list")

    paths = []
    for item in items:
        if isinstance(item, dict):
            if "field" not in item or set(item) - {"field", "from"}:
                raise ValueError("unnest requires field and an optional from")
            source = item.get("from", primary)
            if not isinstance(source, str) or source not in sources:
                raise ValueError("unnest.from must name the primary or a joined collection")
            item = _path(item["field"])
            if source != primary and not item.startswith(source + "."):
                item = source + "." + item
        paths.append(_path(item))
    return paths


def _expression(value):
    """Parse count(*) or an aggregate over a field or size(field).

    Represent each part as (operator, argument). For example, avg(size(items))
    becomes ("avg", ("size", ("field", "items"))). Only one size call is allowed.
    """
    if not isinstance(value, str):
        raise TypeError("Aggregate expression must be a string")

    match = re.fullmatch(r"(\w+)\((.*)\)", value.strip())
    if match and match[1].lower() == "count" and match[2].strip() == "*":
        return "count", None
    if not match or match[1].lower() not in {"sum", "avg", "min", "max"}:
        raise ValueError(
            "Supported aggregates are sum, avg, min and max over a field or size(field), plus count(*)"
        )

    argument = match[2].strip()
    nested = re.fullmatch(r"(\w+)\((.*)\)", argument)
    if nested:
        if nested[1].lower() != "size":
            raise ValueError("Only size(field) is supported inside an aggregate")
        operand = ("size", ("field", _path(nested[2].strip())))
    else:
        operand = ("field", _path(argument))
    return match[1].lower(), operand


def _match(operations):
    """Copy scalar equality predicates after validating paths and values.

    Reject nulls, containers and non-finite numbers. Their comparison semantics
    are outside the shared template subset.
    """
    if "match" not in operations:
        return None
    predicates = operations["match"]
    if not isinstance(predicates, dict):
        raise ValueError("match must be a dictionary of scalar equality predicates")
    for path, value in predicates.items():
        _path(path)
        if value is None or not isinstance(value, (str, bool, int, float)):
            raise ValueError("Only non-null scalar equality predicates are supported")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Predicate numbers must be finite")
    return dict(predicates)


def _template(template):
    """Validate all optional operations and extract their parts.

    Return the primary collection, grouping field, expressions, array paths,
    predicates, joins, projection, sort and limit. Both translators use this representation.

    The input template is only read, never changed. Unsupported structures raise
    ValueError. Incorrect template or expression types raise TypeError.
    """
    if not isinstance(template, dict):
        raise TypeError("template must be a dictionary")

    # Check the operation set before interpreting its contents.
    primary = _identifier(template.get("primary_collection"), "primary_collection")
    operations = template.get("operations")
    if not isinstance(operations, dict) or set(operations) - {
        "group",
        "unnest",
        "match",
        "join",
        "project",
        "sort",
        "limit",
    }:
        raise ValueError("Unsupported template operation")
    joins = _joins(operations, primary)
    unnests = _unnests(operations, primary, joins)

    by, expressions = None, {}
    if "group" in operations:
        # Preserve whether by is a scalar or a list, including single-item lists.
        group = operations["group"]
        if not isinstance(group, dict) or set(group) != {"by", "aggregates"}:
            raise ValueError("group requires by and aggregates")

        by = group["by"]
        paths = by if isinstance(by, list) else [by]
        if not paths:
            raise ValueError("At least one grouping field is required")
        aliases = [_path(path).replace(".", "_") for path in paths]
        if len(set(aliases)) != len(aliases):
            raise ValueError("Grouping output aliases must be distinct")
        aggregates = group["aggregates"]
        if not isinstance(aggregates, dict):
            raise ValueError("group.aggregates must be a dictionary")

        # Record each output name with its aggregate function and input path.
        expressions = {}
        for alias, expr in aggregates.items():
            _identifier(alias, "Aggregate alias")
            if alias in {*aliases, "_id"}:
                raise ValueError("Aggregate alias must not collide with the group field or _id")

            expressions[alias] = _expression(expr)

    projection = operations.get("project")
    if "project" in operations:
        if "group" in operations:
            raise ValueError("Post-group projection is not supported")
        if not isinstance(projection, dict) or not projection:
            raise ValueError("Projection must be a nonempty inclusion mapping")
        for path, include in projection.items():
            _path(path)
            if type(include) is not int or include != 1:
                raise ValueError("Only inclusion projections are supported")
        projection = dict(projection)

    sort = operations.get("sort")
    if "sort" in operations:
        if (
            not isinstance(sort, dict)
            or set(sort) != {"field", "direction"}
            or type(sort["direction"]) is not int
            or sort["direction"] not in {-1, 1}
        ):
            raise ValueError("Sort requires field and direction (-1 or 1)")
        _path(sort["field"])
        if by is not None and sort["field"] not in expressions:
            raise ValueError("Grouped sorting supports aggregate aliases only")
        if projection is not None and sort["field"] not in projection:
            raise ValueError("Sort field must be included in projection")
        sort = dict(sort)

    limit = operations.get("limit")
    if "limit" in operations and (type(limit) is not int or limit <= 0):
        raise ValueError("Limit must be a positive integer")
    return primary, by, expressions, unnests, _match(operations), joins, projection, sort, limit


def translate_mongodb(template: dict, *, database: str) -> MongoAggregateQuery:
    """Translate grouping, array expansion and aggregates into a MongoDB aggregation.

    Args:
        template: JSONBench template with optional join, unnest, match, group,
            project, sort and limit. Projection is inclusion-only and cannot follow
            grouping. See the query guide for expression and sorting restrictions.
        database: MongoDB database name, expressed as a simple identifier.

    Returns:
        A query targeting the template's primary_collection in database.

    Raises:
        TypeError: Incorrect template or expression type.
        ValueError: Unsupported operation, expression or identifier.

    Does not mutate the template, connect to a database, or create indexes.
    """
    _identifier(database, "database")
    primary, by, expressions, unnests, predicates, joins, projection, sort, limit = _template(
        template
    )

    def compile_node(node):
        """Translate a field or function to its native MongoDB expression."""
        operator, argument = node
        if operator == "field":
            return "$" + argument
        if operator == "count":
            return {"$sum": 1}
        return {"$" + operator: compile_node(argument)}

    if by is not None:
        # MongoDB stores the grouping key in _id.
        if isinstance(by, list):
            group_key = {path.replace(".", "_"): "$" + path for path in by}
        else:
            group_key = {by.replace(".", "_"): "$" + by} if "." in by else "$" + by
        group_stage = {"_id": group_key}
        for alias, expression in expressions.items():
            group_stage[alias] = compile_node(expression)

    # Filter expanded rows before counting or aggregating them.
    pipeline = []
    for join in joins:
        pipeline.append({"$lookup": {**join, "as": join["from"]}})
        # Dropping empty lookup arrays gives the original inner-join behavior.
        pipeline.append({"$unwind": "$" + join["from"]})
    pipeline.extend({"$unwind": "$" + path} for path in unnests)
    if predicates is not None:
        pipeline.append({"$match": predicates})
    if by is not None:
        pipeline.append({"$group": group_stage})
    if projection is not None:
        pipeline.append({"$project": projection})
    if sort is not None:
        pipeline.append({"$sort": {sort["field"]: sort["direction"]}})
    if limit is not None:
        pipeline.append({"$limit": limit})

    return MongoAggregateQuery(
        collection=MongoCollectionRef(database, primary),
        pipeline=pipeline,
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
    primary, by, expressions, unnests, predicates, joins, projection, sort, limit = _template(
        template
    )

    # UNNEST changes how later field paths refer to the array elements.
    replacements = {}
    collections = {primary} | {join["from"] for join in joins}

    def quoted(path):
        """Quote each validated path component separately."""
        return ".".join(f"`{part}`" for part in path.split("."))

    def resolve(path):
        """Resolve array aliases before adding the primary collection name."""
        for original in sorted(replacements, key=len, reverse=True):
            if path == original or path.startswith(original + "."):
                return quoted(replacements[original] + path[len(original) :])
        if path.split(".")[0] in collections:
            return quoted(path)
        return quoted(primary + "." + path)

    clauses = [
        f"JOIN {quoted(join['from'])} ON {quoted(primary + '.' + join['localField'])} = "
        f"{quoted(join['from'] + '.' + join['foreignField'])}"
        for join in joins
    ]
    for index, path in enumerate(unnests):
        alias = f"__unnest_{index}"
        while alias in collections:
            alias += "_"
        clauses.append(f"UNNEST {resolve(path)} AS {quoted(alias)}")
        replacements[path] = alias

    def compile_node(node):
        """Resolve fields and translate size to SQL++ ARRAY_LENGTH."""
        operator, argument = node
        if operator == "field":
            return resolve(argument)
        if operator == "count":
            return "COUNT(*)"
        function = "ARRAY_LENGTH" if operator == "size" else operator.upper()
        return f"{function}({compile_node(argument)})"

    paths = (by if isinstance(by, list) else [by]) if by is not None else []
    fields = []
    for path in paths:
        group_alias = path.replace(".", "_")
        fields.append(f"{resolve(path)} AS {quoted(group_alias)}")
    for alias, expression in expressions.items():
        fields.append(f"{compile_node(expression)} AS {quoted(alias)}")

    if projection is not None:
        fields = [f"{resolve(path)} AS {quoted(path.replace('.', '_'))}" for path in projection]
    select = ", ".join(fields) if fields else "*"

    # Keep the original statement form. The context supplies its bucket and scope.
    parts = [f"SELECT {select} FROM {quoted(primary)}", *clauses]
    if predicates:
        # JSON encoding escapes strings without changing the original SQL++ form.
        conditions = [
            f"{resolve(path)} = {json.dumps(value, ensure_ascii=True, allow_nan=False)}"
            for path, value in predicates.items()
        ]
        parts.append("WHERE " + " AND ".join(conditions))
    if by is not None:
        parts.append("GROUP BY " + ", ".join(resolve(path) for path in paths))
    if sort is not None:
        key = (
            quoted(sort["field"].replace(".", "_"))
            if by is not None or projection is not None
            else resolve(sort["field"])
        )
        parts.append(f"ORDER BY {key} {'ASC' if sort['direction'] == 1 else 'DESC'}")
    if limit is not None:
        parts.append(f"LIMIT {limit}")
    return CouchbaseQuery(
        statement=" ".join(parts) + ";",
        query_context=f"default:`{bucket}`.`{scope}`",
    )
