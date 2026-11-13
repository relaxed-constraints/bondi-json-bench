# Changelog

## Unreleased

- Add Couchbase deployment and loading to the walkthrough, using the same generated
  dataset as MongoDB. Include the BONDI Couchbase extra and separate cleanup.

- Extend the walkthrough with local MongoDB deployment, per-collection BONDI
  loading and an explicit cleanup cell.

- Add a walkthrough notebook with the travel-data generation example.

- Add `json_bench.data.generate_travel_dataset()` with the existing JSONBench
  generation semantics. Return four document lists without file or database I/O.
- Pin Faker to JSONBench's version, 38.3.0. Add fixed-output compatibility,
  relationship, repeatability and input-validation tests.
- Remove the obsolete greeting scaffolding after removal of the greeting module
  and notebook.
