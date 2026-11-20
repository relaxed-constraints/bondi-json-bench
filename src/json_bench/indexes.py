"""Resume-safe baseline inspection; BONDI owns index definitions and creation."""

import math
import re
from datetime import timedelta

from bondi import CouchbaseConnection, FieldIndex, IndexSet, MongoConnection
from bondi.couchbase import create_couchbase_indexes
from bondi.mongodb import create_mongo_indexes
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from pymongo import MongoClient


def validate_indexes(indexes: IndexSet, timeout_seconds=300) -> None:
    """Validate the shared baseline before any database operations.

    Args:
        indexes: Collection-keyed BONDI IndexSet containing only FieldIndex definitions.
        timeout_seconds (float): Positive finite per-operation timeout in seconds.

    Native index types need their own equivalence policy and are not accepted here.
    """
    if not isinstance(indexes, IndexSet):
        raise TypeError("indexes must be an IndexSet")
    indexes.validate()
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("timeout_seconds must be positive and finite")
    for definitions in indexes.values():
        names = set()
        for index in definitions:
            if type(index) is not FieldIndex:
                raise TypeError("Baseline indexes must be FieldIndex definitions")
            if index.resolved_name in names:
                raise ValueError("Duplicate index name in collection")
            names.add(index.resolved_name)


def ensure_mongodb_indexes(
    connection: MongoConnection, indexes: IndexSet, *, timeout_seconds=300
) -> dict:
    """Reuse matching baseline indexes and create missing ones through BONDI.

    Args:
        connection: MongoDB connection settings for the running travel database.
        indexes: Collection-keyed IndexSet of shared field definitions.
        timeout_seconds (float): Positive finite timeout per operation.

    Returns:
        Collection names mapped to requested index names in definition order.

    Inspect every requested index before creating any. Reject conflicting keys or
    options; leave unrelated indexes untouched. Native errors propagate, including
    BONDI IndexCreationError for partially completed creation batches. Run without
    concurrent index changes. Clients are closed on success or failure.
    """
    validate_indexes(indexes, timeout_seconds)
    if not isinstance(connection, MongoConnection):
        raise TypeError("connection must be a MongoConnection")
    pending, names = {}, {}
    credentials = {
        key: value
        for key, value in (("username", connection.username), ("password", connection.password))
        if value is not None
    }
    with MongoClient(connection.uri, timeoutMS=timeout_seconds * 1000, **credentials) as client:
        for collection, definitions in indexes.items():
            existing = {
                index["name"]: index for index in client["travel"][collection].list_indexes()
            }
            pending[collection], names[collection] = [], []
            for definition in definitions:
                is_id = definition.keys == (("_id", 1),)
                name = "_id_" if is_id else definition.resolved_name
                if is_id and definition.name not in (None, "_id_"):
                    raise ValueError("The built-in _id index requires its default name")
                if name == "_id_" and not is_id:
                    raise ValueError("_id_ is reserved for the built-in index")
                names[collection].append(name)
                index = existing.get(name)
                if index is None:
                    pending[collection].append(definition)
                    continue
                plain = (
                    not any(
                        index.get(option)
                        for option in ("sparse", "partialFilterExpression", "collation", "hidden")
                    )
                    and (is_id or not index.get("unique"))
                    and "expireAfterSeconds" not in index
                )
                if list(index["key"].items()) != list(definition.keys) or not plain:
                    raise ValueError(f"Conflicting MongoDB index: {collection}.{name}")
    if any(pending.values()):
        create_mongo_indexes(
            connection, indexes=IndexSet(pending), database="travel", timeout=timeout_seconds
        )
    return names


def _matching_key(expression, field, direction):
    """Match plain field keys, allowing the server to omit default ASC."""
    expression = expression.strip()
    match = re.search(r"\s+(ASC|DESC)$", expression, re.IGNORECASE)
    observed_direction = 1
    if match:
        observed_direction = 1 if match[1].upper() == "ASC" else -1
        expression = expression[: match.start()].strip()
    quoted = ".".join("`" + part.replace("`", "``") + "`" for part in field.split("."))
    # Unquoted names only represent paths for simple SQL++ identifiers.
    allowed = [quoted]
    if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*", field):
        allowed.append(field)
    return expression in allowed and observed_direction == direction


def ensure_couchbase_indexes(
    connection: CouchbaseConnection, indexes: IndexSet, *, timeout_seconds=300
) -> dict:
    """Reuse matching secondary indexes and create missing ones through BONDI.

    Args:
        connection: Couchbase connection settings for the running travel._default collections.
        indexes: Collection-keyed IndexSet of shared field definitions.
        timeout_seconds (float): Positive finite timeout per operation, in seconds.

    Returns:
        Collection names mapped to requested index names in definition order.

    Existing keys, ordering, primary status, predicates and partitioning must match
    the plain baseline. All conflicts are checked before creation. Matching existing
    indexes are watched until online, including on resume; BONDI waits for new ones.
    Deferred existing builds are started before watching. Unrelated indexes are
    retained. Preparation must run without concurrent DDL. Clients always close.
    """
    validate_indexes(indexes, timeout_seconds)
    if not isinstance(connection, CouchbaseConnection):
        raise TypeError("connection must be a CouchbaseConnection")
    timeout = timedelta(seconds=timeout_seconds)
    pending, names, reused, deferred = {}, {}, {}, []
    cluster = Cluster(
        connection.uri,
        ClusterOptions(PasswordAuthenticator(connection.username, connection.password)),
    )
    try:
        scope = cluster.bucket("travel").scope("_default")
        for collection, definitions in indexes.items():
            manager = scope.collection(collection).query_indexes()
            existing = {index.name: index for index in manager.get_all_indexes(timeout=timeout)}
            pending[collection], names[collection], reused[collection] = [], [], []
            for definition in definitions:
                name = definition.resolved_name
                names[collection].append(name)
                index = existing.get(name)
                if index is None:
                    pending[collection].append(definition)
                    continue
                if (
                    index.is_primary
                    or index.condition
                    or index.partition
                    or len(index.index_key) != len(definition.keys)
                    or not all(
                        _matching_key(expr, field, direction)
                        for expr, (field, direction) in zip(
                            index.index_key, definition.keys, strict=True
                        )
                    )
                ):
                    raise ValueError(f"Conflicting Couchbase index: {collection}.{name}")
                reused[collection].append(name)
                if index.state == "deferred":
                    deferred.append((collection, name))
        # Build only requested deferred indexes, never unrelated definitions.
        for collection, name in deferred:

            def quote(value):
                return "`" + value.replace("`", "``") + "`"

            cluster.query(
                f"BUILD INDEX ON `travel`.`_default`.{quote(collection)} ({quote(name)})",
                timeout=timeout,
            ).execute()
        if any(pending.values()):
            create_couchbase_indexes(
                connection,
                indexes=IndexSet(pending),
                bucket="travel",
                scope="_default",
                timeout=timeout_seconds,
            )
        for collection, existing_names in reused.items():
            if existing_names:
                scope.collection(collection).query_indexes().watch_indexes(
                    existing_names, timeout=timeout
                )
    finally:
        cluster.close()
    return names
