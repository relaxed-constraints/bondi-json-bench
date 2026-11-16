"""Resume inspection delegates missing definitions to BONDI."""

from types import SimpleNamespace as S
from unittest.mock import MagicMock

import pytest
from bondi import IndexSet

from json_bench import indexes as mod


@pytest.fixture
def clients(monkeypatch):
    mongo, cluster = MagicMock(), MagicMock()
    monkeypatch.setattr(mod, "MongoClient", mongo)
    monkeypatch.setattr(mod, "Cluster", cluster)
    creators = [MagicMock(), MagicMock()]
    monkeypatch.setattr(mod, "create_mongo_indexes", creators[0])
    monkeypatch.setattr(mod, "create_couchbase_indexes", creators[1])
    db = mongo.return_value.__enter__.return_value["travel"]
    manager = cluster.return_value.bucket.return_value.scope.return_value.collection.return_value.query_indexes.return_value
    db["bookings"].list_indexes.return_value = []
    manager.get_all_indexes.return_value = []
    return db, manager, creators, cluster


def spec():
    return IndexSet.from_dict({"bookings": [{"fields": ["tour_id"], "name": "baseline"}]})


def deployment():
    return S(uri="unused", username="user", password="password")


def test_mongo_create_and_repeat(clients):
    db, _, creators, _ = clients
    assert mod.ensure_mongodb_indexes(deployment(), spec()) == {"bookings": ["baseline"]}
    assert creators[0].call_args.kwargs["indexes"].to_dict() == spec().to_dict()
    creators[0].reset_mock()
    db["bookings"].list_indexes.return_value = [{"name": "baseline", "key": {"tour_id": 1}}]
    mod.ensure_mongodb_indexes(deployment(), spec())
    creators[0].assert_not_called()


@pytest.mark.parametrize(
    "extra",
    [
        {"key": {"other": 1}},
        {"unique": True},
        {"sparse": True},
        {"partialFilterExpression": {"x": 1}},
        {"expireAfterSeconds": 0},
        {"hidden": True},
    ],
)
def test_mongo_conflict(clients, extra):
    db, _, creators, _ = clients
    db["bookings"].list_indexes.return_value = [
        {"name": "baseline", "key": {"tour_id": 1}, **extra}
    ]
    with pytest.raises(ValueError, match="Conflicting"):
        mod.ensure_mongodb_indexes(deployment(), spec())
    creators[0].assert_not_called()


def existing(**changes):
    return S(
        **dict(
            dict(
                name="baseline",
                is_primary=False,
                index_key=["`tour_id` ASC"],
                condition=None,
                partition=None,
                state="online",
            ),
            **changes,
        )
    )


def test_couchbase_create_repeat_and_wait(clients):
    _, manager, creators, cluster = clients
    mod.ensure_couchbase_indexes(deployment(), spec())
    assert creators[1].call_args.kwargs["indexes"].to_dict() == spec().to_dict()
    creators[1].reset_mock()
    manager.get_all_indexes.return_value = [existing()]
    mod.ensure_couchbase_indexes(deployment(), spec())
    creators[1].assert_not_called()
    assert manager.watch_indexes.call_args.args == (["baseline"],)
    assert cluster.return_value.close.call_count == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"index_key": ["wrong"]},
        {"index_key": ["`tour_id` DESC"]},
        {"is_primary": True},
        {"condition": "x = 1"},
        {"partition": "HASH(x)"},
    ],
)
def test_couchbase_conflict(clients, changes):
    _, manager, creators, cluster = clients
    manager.get_all_indexes.return_value = [existing(**changes)]
    with pytest.raises(ValueError, match="Conflicting"):
        mod.ensure_couchbase_indexes(deployment(), spec())
    creators[1].assert_not_called()
    cluster.return_value.close.assert_called_once()


def test_deferred_resume_and_timeout(clients):
    _, manager, _, cluster = clients
    manager.get_all_indexes.return_value = [existing(state="deferred")]
    manager.watch_indexes.side_effect = TimeoutError("not ready")
    with pytest.raises(TimeoutError):
        mod.ensure_couchbase_indexes(deployment(), spec())
    cluster.return_value.query.return_value.execute.assert_called_once()
    cluster.return_value.close.assert_called_once()


@pytest.mark.parametrize("helper", [mod.ensure_mongodb_indexes, mod.ensure_couchbase_indexes])
def test_old_mapping_rejected_before_connection(clients, helper):
    with pytest.raises(TypeError, match="IndexSet"):
        helper(deployment(), {"bookings": ["tour_id"]})
    assert not clients[2][0].called and not clients[2][1].called


def test_partial_batch_resume(clients):
    db, _, creators, _ = clients
    db["bookings"].list_indexes.return_value = [{"name": "baseline", "key": {"tour_id": 1}}]
    indexes = IndexSet.from_dict(
        {
            "bookings": [
                {"fields": ["tour_id"], "name": "baseline"},
                {"fields": ["customer_id"], "name": "second"},
            ]
        }
    )
    mod.ensure_mongodb_indexes(deployment(), indexes)
    pending = creators[0].call_args.kwargs["indexes"]
    assert [index.name for index in pending["bookings"]] == ["second"]


def test_later_collection_conflict_prevents_all_creation(clients):
    db, _, creators, _ = clients
    first, second = MagicMock(), MagicMock()
    first.list_indexes.return_value = []
    second.list_indexes.return_value = [{"name": "conflict", "key": {"wrong": 1}}]
    db.__getitem__.side_effect = {"first": first, "second": second}.__getitem__
    indexes = IndexSet.from_dict(
        {
            "first": [{"fields": ["x"], "name": "missing"}],
            "second": [{"fields": ["x"], "name": "conflict"}],
        }
    )
    with pytest.raises(ValueError, match="Conflicting"):
        mod.ensure_mongodb_indexes(deployment(), indexes)
    creators[0].assert_not_called()
