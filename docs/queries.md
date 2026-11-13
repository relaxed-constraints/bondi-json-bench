# Query translation

Translate a JSONBench template into native BONDI query objects. The supported templates are Q1 (total booking value per tour) and Q2
(average, minimum and maximum traveller age per tour), plus Q3
(average traveller group size per booking, grouped by tour), and Q4
(itinerary visits to a location, grouped by difficulty).
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

Use `group` with one simple field name for `by`. Aggregates support `sum`, `avg`,
`min` and `max` over simple or dotted field paths, or `size(field)`. Add an optional `unnest` list
before grouping. Each item is a path or `{"field": "travellers", "from": "bookings"}`.
The optional `from` must name the primary collection. Each identifier component
must match `[A-Za-z_][A-Za-z_0-9]*`.
Equality filters use `match`, a mapping from field paths to non-null scalar values.
Multiple predicates are combined with AND. Numbers must be finite.
Use `count(*)` to count rows after array expansion and filtering.
Joins, other filters, sorting, limits, compound grouping and nested functions other than `size(field)` remain unsupported.
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

`tests/fixtures/q1_translation.json` `q2_translation.json` `q3_translation.json` and `q4_translation.json` contain outputs captured from the
corrected JSONBench translators. Each fixture records the source commit and file checksums.
Tests compare the entire pipeline and SQL++ statement, plus BONDI destination metadata.
They need no JSONBench checkout at runtime.

These tests establish translation compatibility. The
[walkthrough](../notebooks/walkthrough.ipynb) executes Q1–Q4 as one BONDI workload per backend
and compares tour IDs and aggregate values, ignoring row order. It uses relative tolerance
1e-9 and absolute tolerance 1e-6 for floating-point sums.

The walkthrough creates the original Couchbase bookings index and uses
REQUEST_PLUS consistency to include newly loaded data. This is a correctness
check, not a benchmark run. Performance comparisons remain a separate step.

## Q2: traveller ages

Q2 expands `travellers` before grouping by `tour_id`. MongoDB uses `$unwind`.
Couchbase uses `UNNEST` with an internal alias, then reads each traveller's `age`.
The aggregates are `avg(travellers.age)`, `min(travellers.age)` and
`max(travellers.age)`. Each traveller contributes once, so this is not an average
of booking averages. Empty arrays contribute no rows.

These semantics apply to the generated travel data, which contains numeric ages
inside arrays. Translation compatibility does not establish cross-database
agreement for arbitrary malformed data, scalar values or mixed types.

The walkthrough calls `run_workload(..., collect_results=True)` for each backend.
BONDI returns results in workload order. The notebook pairs them with the same
ordered template list, then compares every aggregate for each tour.

## Q3: traveller group size

Q3 groups bookings by `tour_id` and evaluates `avg(size(travellers))`.
Each booking contributes its array length. There is no array expansion.
For example, two bookings with two and four travellers give an average of three.
An empty array contributes zero and its booking remains in the average.

MongoDB uses `{"$avg": {"$size": "$travellers"}}` inside `$group`.
Couchbase uses ``AVG(ARRAY_LENGTH(`bookings`.`travellers`))`` in SQL++.
The translator supports one `size(field)` call inside `sum`, `avg`, `min` or `max`.
It rejects nested aggregates and repeated `size` calls.

The generated data always supplies traveller arrays. We preserve the original
queries without adding null handling or type conversions. Cross-database
agreement for missing, null or non-array values is outside this contract.

## Q4: itinerary visits

Q4 expands `itinerary`, matches `itinerary.location`, then groups by `difficulty`.
Its `count(*)` becomes MongoDB's `{"$sum": 1}` or Couchbase's `COUNT(*)`.
The filter becomes `$match` or a SQL++ `WHERE` clause. SQL++ values use JSON
encoding to escape quotes and other special characters.

The output remains named `num_of_tours` for compatibility. It counts visits,
not distinct tours: two matching itinerary entries in one tour contribute two.
Groups with no matching visits do not appear.

The notebook selects a location from the generated tours to produce a nonempty
example. It creates the original `tours-id` index and compares counts by difficulty.
The reference fixture retains the original template's `Donnafurt` value.
