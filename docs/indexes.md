# Baseline indexes

The definitions in `experiments/indexes.json` are grouped by backend, then by
collection. Each collection contains BONDI FieldIndex definitions:

```json
{
  "mongodb": {
    "bookings": [{"fields": ["tour_id"], "name": "tour_id_1"}]
  },
  "couchbase": {
    "bookings": [{"fields": ["tour_id"], "name": "bookings-tour_id"}]
  }
}
```

Each entry defines one index. `fields: ["a", "b"]` defines a compound ascending
index; use `keys: [["a", 1], ["b", -1]]` for explicit directions. Names are
explicit in the shipped baseline to preserve the existing experiment definitions.

| Field | MongoDB | Couchbase |
|---|---|---|
| tours._id | Automatic index | Secondary index named `tours-id` |
| bookings.tour_id | `tour_id_1` | `bookings-tour_id` |
| reviews.tour_id | `tour_id_1` | `reviews-tour_id` |

## Loading and saving

```python
import json
from pathlib import Path
from bondi import IndexSet

config = json.loads(Path("experiments/indexes.json").read_text())
indexes = IndexSet.from_dict(config["mongodb"])
indexes.save("indexes.mongodb.json")
indexes = IndexSet.load("indexes.mongodb.json")
```

Preparation saves `indexes.mongodb.json` and `indexes.couchbase.json` in BONDI's
versioned persistence format. The combined `indexes.json` records the input
configuration. `index_names.mongodb.json` and `index_names.couchbase.json` record
names after successful creation for each backend.

## Creation and resume

```python
from json_bench.indexes import ensure_mongodb_indexes, ensure_couchbase_indexes

names = ensure_mongodb_indexes(mongo_deployment.connection, indexes)
names = ensure_couchbase_indexes(
    couchbase_deployment.connection, IndexSet.from_dict(config["couchbase"]), timeout_seconds=300
)
```

Supply `deployment.connection` for a managed instance, or a `MongoConnection` /
`CouchbaseConnection` for an external instance. The database must already be running.
These helpers inspect all requested indexes, reuse matching names, and delegate
missing definitions to BONDI's backend
`create_mongo_indexes()` or `create_couchbase_indexes()` function. They own and close their inspection clients.
MongoDB uses database `travel`; Couchbase uses bucket `travel`, scope `_default`.

Conflicting named definitions raise `ValueError` before creating missing indexes.
Keys, directions and relevant native options must match the plain field definition.
Couchbase matching indexes are watched until online; requested deferred indexes
are built first. Unrelated indexes are left untouched. Run without concurrent DDL.
Equivalent MongoDB indexes with different names follow native conflict rules.
Errors propagate, including BONDI's partial-batch creation errors; retrying inspects
what already exists and creates only missing definitions.

Only shared FieldIndex definitions are accepted by these experiment helpers.
Native MongoIndex and CouchbaseIndex features require separate equivalence policies.
The old collection-to-field-string format is no longer supported. Resume remains
supported for new runs with unchanged preparation plans; old saved plans require
a new experiment rather than automatic conversion.
