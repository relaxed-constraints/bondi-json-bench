# Query translation

Translate a JSONBench template into native BONDI query objects. This first version
supports Q1: group bookings by tour ID and sum their stored total prices.
Translation does not connect to a database, execute queries or create indexes.

```python
from json_bench.queries import translate_couchbase, translate_mongodb

q1 = {
    "name": "Query 1",
    "description": "Total booking value per tour",
    "primary_collection": "bookings",
    "operations": {
        "group": {
            "by": "tour_id",
            "aggregates": {"total_revenue": "sum(total_price)"},
        },
    },
}

mongo_query = translate_mongodb(q1, database="travel")
couchbase_query = translate_couchbase(q1, bucket="travel", scope="_default")
```

## API

```python
translate_mongodb(template: dict, *, database: str) -> MongoAggregateQuery
translate_couchbase(template: dict, *, bucket: str, scope: str = "_default") -> CouchbaseQuery
```

The template supplies the collection name. The other arguments supply its database
or bucket and scope. Each call returns a fresh BONDI object and leaves the template
unchanged. Name and description are metadata and do not change the query.

Only the `group` operation is supported. Use one simple field name for `by` and
one or more `sum(field)` aggregates. Identifiers must match
`[A-Za-z_][A-Za-z_0-9]*`, including destination names. Dotted paths, joins, arrays,
filters, sorting, limits and other aggregates are not yet supported.
An aggregate alias cannot equal `_id` or the grouping field.

Unsupported values raise `ValueError`. A non-dictionary template or non-string
aggregate expression raises `TypeError`. Unsupported operations are never ignored.

## Generated queries

MongoDB targets `MongoCollectionRef("travel", "bookings")` with this pipeline:

```python
[{"$group": {"_id": "$tour_id", "total_revenue": {"$sum": "$total_price"}}}]
```

Couchbase uses the following statement, with query context
`default:` followed by the quoted bucket and scope: ``default:`travel`.`_default` ``.

```sql
SELECT `bookings`.`tour_id` AS `tour_id`,
       SUM(`bookings`.`total_price`) AS `total_revenue`
FROM `bookings`
GROUP BY `bookings`.`tour_id`;
```

The implementation emits a single-line statement, exactly as corrected JSONBench does.
Neither query filters on payment or travel status, joins tours, or rounds the sum.
Only tour IDs represented in bookings appear. Result order is unspecified.
MongoDB names the grouping field `_id`; Couchbase names it `tour_id`.

## Compatibility checks

`tests/fixtures/q1_translation.json` contains Q1 and outputs captured from the
corrected JSONBench translators. It records the source commit and file checksums.
Tests compare the entire pipeline and SQL++ statement, plus BONDI destination metadata.
They need no JSONBench checkout at runtime.

These tests establish translation compatibility. Live result equivalence and
benchmark performance comparisons are separate next steps.
See the [walkthrough](../notebooks/walkthrough.ipynb) to inspect both query objects.
