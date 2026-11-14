# Baseline indexes

The experiment definitions live in `experiments/indexes.json`. Each collection
maps to a list of fields. Each field creates a separate single-field ascending
index, not one compound index. Only simple field and collection names are supported.

The baseline matches corrected JSONBench:

| Field | MongoDB | Couchbase |
|---|---|---|
| tours._id | Automatic index | Secondary index |
| bookings.tour_id | Secondary index | Secondary index |
| reviews.tour_id | Secondary index | Secondary index |

## API

```python
from json_bench.indexes import ensure_mongodb_indexes, ensure_couchbase_indexes

ensure_mongodb_indexes(database, indexes: dict[str, list[str]]) -> None
ensure_couchbase_indexes(scope, indexes: dict[str, list[str]], *, timeout_seconds=300) -> None
```

Supply a native PyMongo Database or Couchbase Scope. The caller owns and closes the client connection. The notebook shows connection setup using BONDI deployment details.

Example:

```python
ensure_mongodb_indexes(database, {"bookings": ["tour_id"], "reviews": ["tour_id"]})
ensure_couchbase_indexes(
    scope,
    {
        "tours": ["_id"],
        "bookings": ["tour_id"],
        "reviews": ["tour_id"],
    },
)
```

MongoDB names these indexes `tour_id_1`. Couchbase uses collection-field names,
with `_id` shortened to `id`: `tours-id`, `bookings-tour_id`, `reviews-tour_id`.
Matching named indexes are reused. Conflicting named definitions raise ValueError.
Equivalent MongoDB indexes with other names follow the native driver's conflict
rules; the helper does not rename or remove them.

These helpers do not create primary Couchbase indexes, covering indexes or array
indexes. Those would be separate experiment policies.
