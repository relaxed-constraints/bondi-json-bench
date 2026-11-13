"""Index preparation contracts using native-client doubles."""

from types import SimpleNamespace as S
from unittest.mock import MagicMock

import pytest

from json_bench.indexes import ensure_couchbase_indexes, ensure_mongodb_indexes


def test_mongo_create_and_repeat():
    db = MagicMock()
    collection = db.__getitem__.return_value
    collection.list_indexes.return_value = []
    ensure_mongodb_indexes(db, {"bookings": ["tour_id"]})
    collection.create_index.assert_called_once_with([("tour_id", 1)], name="tour_id_1")
    collection.create_index.reset_mock()
    collection.list_indexes.return_value = [{"name": "tour_id_1", "key": {"tour_id": 1}}]
    ensure_mongodb_indexes(db, {"bookings": ["tour_id"]})
    collection.create_index.assert_not_called()


@pytest.mark.parametrize(
    "extra",
    [
        {"key": {"other": 1}},
        {"unique": True},
        {"sparse": True},
        {"partialFilterExpression": {"x": 1}},
        {"expireAfterSeconds": 0},
    ],
)
def test_mongo_conflict(extra):
    db = MagicMock()
    db.__getitem__.return_value.list_indexes.return_value = [
        {"name": "tour_id_1", "key": {"tour_id": 1}, **extra}
    ]
    with pytest.raises(ValueError, match="Conflicting"):
        ensure_mongodb_indexes(db, {"bookings": ["tour_id"]})
    db.__getitem__.return_value.create_index.assert_not_called()


def test_couchbase_create_repeat_and_wait():
    scope = MagicMock()
    manager = scope.collection.return_value.query_indexes.return_value
    manager.get_all_indexes.return_value = []
    ensure_couchbase_indexes(scope, {"tours": ["_id"]})
    assert manager.create_index.call_args.args == ("tours-id", ["`_id`"])
    assert manager.watch_indexes.call_args.args == (["tours-id"],)
    manager.create_index.reset_mock()
    manager.get_all_indexes.return_value = [
        S(name="tours-id", is_primary=False, index_key=["`_id`"], condition=None, partition=None)
    ]
    ensure_couchbase_indexes(scope, {"tours": ["_id"]})
    manager.create_index.assert_not_called()
    assert manager.watch_indexes.call_count == 2


def test_couchbase_conflict_and_timeout():
    scope = MagicMock()
    manager = scope.collection.return_value.query_indexes.return_value
    manager.get_all_indexes.return_value = [
        S(name="tours-id", is_primary=False, index_key=["wrong"], condition=None, partition=None)
    ]
    with pytest.raises(ValueError, match="Conflicting"):
        ensure_couchbase_indexes(scope, {"tours": ["_id"]})
    manager.get_all_indexes.return_value = []
    manager.watch_indexes.side_effect = TimeoutError("not ready")
    with pytest.raises(TimeoutError):
        ensure_couchbase_indexes(scope, {"tours": ["_id"]})


@pytest.mark.parametrize("spec", [[], {"tours": "_id"}, {"tours": ["a.b"]}, {"bad;": ["_id"]}])
def test_validation_before_database_calls(spec):
    client = MagicMock()
    for helper in [ensure_mongodb_indexes, ensure_couchbase_indexes]:
        with pytest.raises(ValueError):
            helper(client, spec)
    assert not client.mock_calls
