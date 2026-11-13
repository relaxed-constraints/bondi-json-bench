# Changelog

## Unreleased

- Add Q6 dotted grouping paths with original MongoDB and Couchbase output shapes.
  Extend reference tests, documentation and notebook workload comparisons.

- Add Q5 joins with corrected JSONBench reference tests. Run Q1–Q5 in the
  walkthrough and compare review averages across both databases.

- Add Q4 scalar equality filters and row counts, with corrected JSONBench fixtures.
  Include Q4 in the notebook workloads and compare results by each grouping field.

- Add Q3 array-length aggregates with corrected JSONBench reference tests.
  Include Q3 in the walkthrough workloads and result comparison.

- Support Q2 array expansion, nested fields and average/minimum/maximum aggregates.
  Preserve corrected JSONBench output and run Q1/Q2 as BONDI workloads in the walkthrough.

- Add live Q1 execution and result comparison to the walkthrough, with the original
  Couchbase bookings index and explicit index consistency for correctness checks.

- Add Q1 MongoDB and Couchbase translation functions returning BONDI query objects.
  Test exact compatibility with corrected JSONBench output and reject unsupported
  operations. Add API documentation and a non-executing walkthrough example.

- Compact the walkthrough into shared deployment, loading and cleanup cells.

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
