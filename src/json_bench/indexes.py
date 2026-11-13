"""Prepare explicit single-field index baselines using native database clients."""

import math
import re
from datetime import timedelta


def _specs(indexes):
    """Validate the complete mapping before making database changes."""
    if not isinstance(indexes, dict):
        raise ValueError("indexes must map collection names to lists of fields")
    specs = []
    identifier = r"[A-Za-z_][A-Za-z_0-9]*"
    for collection, fields in indexes.items():
        if not isinstance(collection, str) or not re.fullmatch(identifier, collection):
            raise ValueError("Collection names must be simple identifiers")
        if not isinstance(fields, list):
            raise ValueError("Each collection must map to a list of fields")
        for field in fields:
            if not isinstance(field, str) or not re.fullmatch(identifier, field):
                raise ValueError("Index fields must be simple identifiers")
            specs.append((collection, field))
    return list(dict.fromkeys(specs))


def ensure_mongodb_indexes(database, indexes: dict[str, list[str]]) -> None:
    """Ensure separate ascending indexes on each listed field.

    Args:
        database: Native pymongo Database. The caller owns its client.
        indexes: Collection-to-fields mapping. Fields are simple names, not paths.

    Existing matching named indexes are reused. Conflicting definitions raise
    ValueError. Index creation blocks until the server completes it. Unrelated
    indexes are retained. Driver errors propagate. Returns None.
    """
    for collection, field in _specs(indexes):
        target = database[collection]
        name = "_id_" if field == "_id" else f"{field}_1"
        existing = list(target.list_indexes())
        for index in existing:
            same_key = list(index["key"].items()) == [(field, 1)]
            plain = (
                not any(
                    index.get(option)
                    for option in ("sparse", "partialFilterExpression", "collation", "hidden")
                )
                and (field == "_id" or not index.get("unique"))
                and "expireAfterSeconds" not in index
            )
            if index["name"] == name and not (same_key and plain):
                raise ValueError(f"Conflicting MongoDB index: {collection}.{name}")
        if not any(list(i["key"].items()) == [(field, 1)] and i["name"] == name for i in existing):
            # The native driver checks conflicts with equivalent indexes under other names.
            target.create_index([(field, 1)], name=name)


def ensure_couchbase_indexes(scope, indexes: dict[str, list[str]], *, timeout_seconds=300) -> None:
    """Ensure separate secondary indexes and wait for each to be online.

    Args:
        scope: Native couchbase Scope. The caller owns its cluster connection.
        indexes: Collection-to-fields mapping. Fields are simple names, not paths.
        timeout_seconds: Positive finite timeout for each management operation.

    Names use collection-field, with _id named id to match corrected JSONBench.
    Conflicting named indexes raise ValueError. Other indexes are left untouched.
    Driver errors propagate. Returns None. Run preparation without concurrent DDL.
    """
    specs = _specs(indexes)
    if (
        not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be positive and finite")
    names = [
        (collection, f"{collection}-{'id' if field == '_id' else field}")
        for collection, field in specs
    ]
    if len(set(names)) != len(names):
        raise ValueError("Index names collide (id and _id use the same suffix)")
    timeout = timedelta(seconds=timeout_seconds)
    for (collection, field), (_, name) in zip(specs, names, strict=True):
        manager = scope.collection(collection).query_indexes()
        existing = {index.name: index for index in manager.get_all_indexes(timeout=timeout)}
        if name in existing:
            index = existing[name]
            if (
                index.is_primary
                or index.index_key not in ([field], [f"`{field}`"])
                or index.condition
                or index.partition
            ):
                raise ValueError(f"Conflicting Couchbase index: {collection}.{name}")
        else:
            manager.create_index(name, [f"`{field}`"], timeout=timeout)
        manager.watch_indexes([name], timeout=timeout)
