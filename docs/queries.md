# Query templates

A template describes a query without choosing a database language. The translator
returns a MongoDB aggregation query or a Couchbase SQL++ query.

The benchmark templates live in `experiments/templates/q1.json` through `q8.json`.

| Query | What it calculates |
| --- | --- |
| Q1 | Total booking value per tour |
| Q2 | Average, minimum, and maximum traveller age per tour |
| Q3 | Average traveller group size per booking, grouped by tour |
| Q4 | Itinerary visits to a specified location, grouped by difficulty |
| Q5 | Average review rating per tour |
| Q6 | Average traveller age per destination |
| Q7 | Traveller-visits per location |
| Q8 | Traveller-weighted review ratings by destination and nationality |

## Translate a template

```python
from json_bench.queries import load_template, translate_couchbase, translate_mongodb

template = load_template("experiments/templates/q1.json")
mongo_query = translate_mongodb(template, database="travel")
couchbase_query = translate_couchbase(template, bucket="travel", scope="_default")
```

The template supplies the collection name. Each translator returns a fresh BONDI
query object and leaves the template unchanged. Name and description fields are
metadata; they do not affect execution.

## Supported operations

Operations run in this order: **join → unnest → match → group or project → sort → limit**.
JSON key order does not change execution order. Every operation is optional.
Empty operations produce a collection scan.

| Operation | Accepted form |
| --- | --- |
| `join` | One mapping or an ordered list with `from`, `localField`, and `foreignField` |
| `unnest` | A list of field paths, or mappings with `field` and optional `from` |
| `match` | Field paths mapped to non-null scalar values; predicates use equality and AND |
| `group` | `by` is a field path or nonempty list of paths; `aggregates` maps aliases to expressions |
| `project` | A nonempty mapping of paths to integer `1` |
| `sort` | One `field` and `direction` of `1` or `-1` |
| `limit` | A positive integer |

Aggregates support `sum`, `avg`, `min`, and `max` over fields or `size(field)`.
`count(*)` counts rows after joins, array expansion, and filtering. Empty
aggregates return distinct grouping keys. Nested aggregate functions are rejected.

Identifier components must match `[A-Za-z_][A-Za-z_0-9]*`. Join source names must
be distinct and cannot equal the primary collection. Numeric filter values must
be finite. Unsupported values or combinations raise errors; they are not ignored.

## Output shapes and ordering

MongoDB places group keys in `_id`. Couchbase returns named group fields. Dotted
paths become aliases with underscores. Composite MongoDB keys use an object
inside `_id`, including a single-item grouping list. Alias collisions are rejected.

Projection is inclusion-only. Computed fields, exclusions, and projection after
grouping are unsupported. MongoDB retains `_id` by default and preserves nested
paths. Couchbase uses flat aliases for projected paths. Ungrouped Couchbase
`SELECT *` wraps documents under collection names; MongoDB returns them directly.
The translators preserve these native shapes.

After grouping, sorting must use an aggregate alias. After projection, it must
use an included field. Equal sort keys have no defined relative order. Use a
unique ordering when a limit must select the same rows in both databases.

## Query weighting details

These details matter when interpreting the paper templates:

- **Q2:** each traveller contributes once. Empty traveller arrays contribute no rows.
- **Q3:** each booking contributes its array length. Empty arrays contribute zero.
- **Q4:** the output field remains `num_of_tours`, but counts matching itinerary
  entries. Two matching entries in one tour contribute two.
- **Q5:** each matching review contributes once. Tours without reviews and orphan
  reviews do not contribute. Joins use stored `_id` values, not Couchbase document keys.
- **Q6:** each traveller in a matching booking contributes to the destination average.
- **Q7:** a booking contributes its traveller count for each itinerary entry.
  Three travellers visiting the same location twice contribute six traveller-visits.
- **Q8:** every review is paired with every matching traveller. Nationality comes
  from the traveller, not the review author. Tours without bookings or reviews
  do not contribute.

For Q8, a tour with two AU travellers and ratings 2 and 4 contributes `[2, 4, 2, 4]`.
Another tour at the same destination with one AU traveller and rating 5 adds `[5]`.
Their average is 3.4. It is not an unweighted average of tour ratings.

These semantics apply to the generated data's arrays and scalar keys. Read the
[equivalence checks](validation.md) for coverage and limits, and the
[query API](reference/queries.md) for function signatures.
