# Travel data generation

Use this function to generate the four JSONBench travel collections without a database:

```python
from json_bench.data import generate_travel_dataset

dataset = generate_travel_dataset(
    scale=0.01,
    seed=23,
    reference_date="2025-11-01",
)
```

## API

```python
generate_travel_dataset(
    *, scale: float, seed: int, reference_date: str
) -> dict[str, list[dict]]
```

All three arguments are required and keyword-only.

- `scale`: A finite number of at least 0.01. Booleans are rejected.
- `seed`: An integer used to seed fresh Python and Faker random generators.
- `reference_date`: An ISO date string, such as `2025-11-01`, used instead of today.

The returned dictionary contains these lists, in this order:

| Key | Document count | Count at scale 0.01 |
| --- | --- | --- |
| `users` | `int(1000 * scale)` | 10 |
| `tours` | `int(200 * scale)` | 2 |
| `bookings` | `int(5000 * scale)` | 50 |
| `reviews` | `int(2500 * scale)` | 25 |

Invalid scale values or malformed date strings raise `ValueError`.
The function creates no files and opens no database connections.
Each call returns independent dictionaries and lists.

## Compatibility with JSONBench

The private generator preserves the existing JSONBench generation order and
random calls. Faker is pinned to 38.3.0, matching JSONBench's lockfile.
Repeatability requires the same inputs and compatible dependency versions.

The data rules are unchanged:

- Guides and ordinary users share the users collection.
- Tours reference guides. Bookings reference ordinary users and tours.
- Travellers are embedded in bookings, not linked to user documents.
- Reviews reference bookings and copy their tour IDs.
- Dates remain ISO strings. IDs retain their original prefixes and sequence.
- Booking dates are independent of tour dates. Reviews do not require the booking
  to be marked travelled. Multiple reviews can reference the same booking.

Tests compare complete collection hashes with outputs captured from the original
JSONBench generator. The reference file records the source commit, source-file
checksum, Faker version and inputs. It requires no JSONBench checkout at test time.
Update reference hashes only after explicitly agreeing to change compatibility.

## Memory and next steps

All documents are held in memory. Scale 200 produces 1.74 million documents,
including nested travellers and review text, so large datasets can need substantial memory.

The underlying generator is private. Streaming and persistence are future steps.
The [walkthrough notebook](../notebooks/walkthrough.ipynb) loads the same generated
dataset into MongoDB and Couchbase through BONDI. No custom dataset class is required.
