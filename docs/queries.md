# Query translation

Translate a JSONBench template into native BONDI query objects. All seven operations
are optional, including `group`. Empty operations produce a collection scan. The supported templates are Q1 (total booking value per tour) and Q2
(average, minimum and maximum traveller age per tour), plus Q3
(average traveller group size per booking, grouped by tour), and Q4
(itinerary visits to a location, grouped by difficulty), plus Q5
(average review rating per tour), Q6 (average traveller age per destination), Q7 (traveller-visits per location), and Q8 (traveller-weighted review ratings).
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

Use `group` with a simple or dotted field path, or a nonempty list of paths, for `by`. Aggregates support `sum`, `avg`,
`min` and `max` over simple or dotted field paths, or `size(field)`. Add an optional `unnest` list
before grouping. Each item is a path or `{"field": "travellers", "from": "bookings"}`.
The optional `from` must name the primary or a joined collection. Each identifier component
must match `[A-Za-z_][A-Za-z_0-9]*`.
Equality filters use `match`, a mapping from field paths to non-null scalar values.
Multiple predicates are combined with AND. Numbers must be finite.
Use `count(*)` to count rows after array expansion and filtering.
Other filters and nested functions other than `size(field)` remain unsupported.
An aggregate alias cannot equal `_id` or the grouping output alias.

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

`tests/fixtures/q1_translation.json` `q2_translation.json` `q3_translation.json` `q4_translation.json` `q5_translation.json` `q6_translation.json` `q7_translation.json` and `q8_translation.json` contain outputs captured from the
corrected JSONBench translators. Each fixture records the source commit and file checksums.
Tests compare the entire pipeline and SQL++ statement, plus BONDI destination metadata.
They need no JSONBench checkout at runtime.

These tests establish translation compatibility. The
[walkthrough](../notebooks/walkthrough.ipynb) executes Q1–Q8 as one BONDI workload per backend
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

## Q5: average review rating

Q5 joins `tours._id` to `reviews.tour_id` and groups by the tour's `_id`.
Each matching review contributes once to `avg(reviews.rating)`.
Tours without reviews and reviews without a matching tour do not contribute.
The join uses stored `_id` values, not Couchbase document keys.

Use `join` with `from`, `localField` and `foreignField`. A single mapping or an
ordered list is accepted. Source collections must be distinct, simple names,
and cannot equal the primary collection. Join fields can be dotted paths.
MongoDB emits `$lookup` followed by `$unwind`, which drops empty lookup arrays.
Couchbase emits an inner `JOIN` and resolves joined fields through the source name.
Joins run before explicit array expansion, filtering and grouping.

The public translation functions stay unchanged. The notebook adds Q5 and the
original Couchbase `reviews-tour_id` index. For joined arrays, `unnest.from` supplies the collection prefix if the field
path does not already include it.
Cross-database equivalence is checked on the generated scalar join keys. Missing,
null or array-valued join keys are outside this equivalence claim.

Run the optional join integration test with:

```sh
JSONBENCH_LIVE=1 uv run pytest tests/test_q5_live.py -q
```

It creates disposable deployments, loads `tests/fixtures/q5_join_data.json`,
and checks expected averages in both databases. The fixture includes multiple
reviews, a tour without reviews and a review without a matching tour. The test
removes its deployments afterward. Docker must be running, and ports 27137,
18391, 18393 and 21330 must be free.

## Q6: traveller age per destination

Q6 joins bookings to tours, expands travellers, and groups by `tours.destination`.
Each traveller in each matching booking contributes to the average age.
This is not an average of tour averages and does not deduplicate travellers.

For dotted grouping paths, MongoDB returns a nested key, such as
`{"_id": {"tours_destination": "Sydney"}, "avg_age": 35}`.
Couchbase returns `{"tours_destination": "Sydney", "avg_age": 35}`.
Dots become underscores in the output alias, as in corrected JSONBench.
An aggregate alias must not collide with that output alias.
The notebook normalises these grouping keys before comparing results.

## Q7: traveller-visits per location

Q7 joins tours to bookings, expands itinerary entries, and groups by
`itinerary.location`. It sums `size(bookings.travellers)` for each location.
Existing operators support this template without translation changes.

Each booking contributes its traveller count once per itinerary entry. A booking
with three travellers and two visits to the same location contributes six there.
This counts traveller-visits, not distinct travellers. Tours without bookings,
or with empty itineraries, contribute nothing. Empty traveller arrays add zero.

The optional live test checks repeated locations, multiple bookings, empty arrays,
an unbooked tour and an orphan booking:

```sh
JSONBENCH_LIVE=1 uv run pytest tests/test_q7_live.py -q
```

It uses disposable deployments and the same ports as the Q5 live test. Run these
live tests sequentially. The test removes its deployments afterward.

## Q8: traveller-weighted review ratings

Q8 joins tours to bookings and reviews, expands `bookings.travellers`, and groups
by destination and traveller nationality. Every review is paired with every
matching traveller. Nationality comes from the traveller, not the review author.

For example, tour A has two AU travellers and ratings 2 and 4. Tour B at the same
destination has one AU traveller and rating 5. Q8 averages [2, 4, 2, 4, 5], giving
3.4. Tours without bookings or reviews do not contribute.

Composite grouping uses an ordered list in `group.by`. MongoDB returns all keys
inside `_id`; Couchbase returns separate fields. Dots become underscores in each
alias. Duplicate aliases and collisions with aggregate names are rejected.
A single-item list still produces an object `_id` in MongoDB, as in JSONBench.

Run `JSONBENCH_LIVE=1 uv run pytest tests/test_q8_live.py -q` to check this weighting
and a second nationality against both databases. It uses the same disposable
ports as the other live tests; run them sequentially.

## Optional operations, projection and top-k queries

The execution order is fixed: join, unnest, match, group or project, sort, limit.
JSON key order does not change that order. A template can omit any operation.
A group with empty `aggregates` returns the distinct grouping keys.

`project` accepts a nonempty mapping of paths to integer 1, such as
`{"name": 1, "details.rank": 1}`. Exclusion and computed expressions are not
supported. Projection after grouping is rejected, matching corrected JSONBench.
MongoDB retains `_id` by default and preserves nested paths. Couchbase flattens
projected paths into aliases such as `details_rank`. Ungrouped Couchbase `SELECT *`
wraps documents under collection aliases; MongoDB returns documents directly.
These native result shapes are preserved by the translators.

`sort` accepts one `field` and a `direction` of 1 or -1. After grouping, the field
must be an aggregate alias. After projection, it must be included in the
projection. `limit` must be a positive integer. Equal sort keys have no defined
relative order. Limiting without a unique ordering can select different rows
across databases; this does not by itself show a translation defect.

```python
template = {
    "primary_collection": "tours",
    "operations": {
        "match": {"difficulty": "easy"},
        "project": {"name": 1},
        "sort": {"field": "name", "direction": 1},
        "limit": 10,
    },
}
```

## Seeded combination validation

`tests/template_cases.py` generates 128 distinct templates using seed 23. Together
with seven hand-written cases, these cover scans, filters, projection, joins,
array expansion, groups, sorting and limits in different combinations.
`tests/fixtures/operator_combinations.json` records corrected JSONBench output
and source hashes for all 135 templates. Tests also reject unsupported combinations.
No sibling checkout is needed to run the tests.

Run the live comparison with Docker available:

```sh
JSONBENCH_LIVE=1 uv run pytest tests/test_operator_combinations_live.py -q
```

It uses disposable deployments on ports 27137, 18391, 18393 and 21330, then removes
them. Run live tests sequentially. This test creates a primary index for collection
scans; it does not change the benchmark notebook's index configuration.

The live comparison normalises known native output shapes, retains duplicate rows,
and checks order when sorting is requested. Seven cases also have independently
specified answers. Generated top-k cases use unique sort keys. Failure messages
include the template and seed/index so a failure can be reproduced.

This is bounded, grammar-guided testing, not proof of equivalence for every
possible template or dataset. The generated data has present scalar fields and
known arrays. Null/missing values, mixed types, projection alias collisions and
other shapes outside this tested contract require separate semantic review.

## Sustained-load walkthrough

The walkthrough uses scale factor 0.1 and runs each backend separately through
BONDI's `generate_load()`. Settings specify query weights, client count, warm-up,
measurement, query timeout and drain allowance. It retains `LoadResult` objects
but not database documents. The inactive database is stopped.

The inspection table includes warm-up and measurement admissions and distinguishes
success, timeout, error and unresolved attempts. Measurement-admission counts may
include drain completions and are not throughput. This short demonstration does
not reproduce the paper's experimental protocol.
