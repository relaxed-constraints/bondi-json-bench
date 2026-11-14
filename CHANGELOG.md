# Changelog

## Unreleased

- Document installation from GitHub with uv or pip and an activated environment.

- Use published BONDI 0.3.1 and remove the editable sibling dependency.
- Add offline CI on Python 3.11–3.14 and GitHub Pages deployment after CI passes.

- Add per-query runtime and outcome plots to the walkthrough using retained load results.

- Add workload-ordered per-query summaries and successful runtime samples using
  the same accounting as run summaries.
- Add reusable runtime box plots and stacked outcome-count plots, with 200 dpi
  defaults, explicit empty samples and early-stop labels.

- Add pure load-result summaries with measurement-window throughput, successful
  runtimes, outcome counts and explicit early-stop indicators. Use them in the walkthrough.

- Add native single-field index helpers and experiment baseline definitions.
  Prepare MongoDB and Couchbase indexes before notebook workloads, with conflict
  checks, repeat-call support and Couchbase readiness waits.

- Extract grouped result comparison into json_bench.validate.compare_results,
  with execution checks, numeric tolerances, duplicate detection and sort checks.
  Use the helper in the walkthrough.

- Move the paper templates to experiments/templates and load them by path in the
  walkthrough. Add a generic load_template() helper with file and object checks.

- Use scale factor 0.1 in the walkthrough and demonstrate sequential sustained
  load with explicit query weights and retained per-invocation observations.

- Support scans, optional grouping, empty aggregate maps, inclusion projection,
  sorting and limits with corrected JSONBench semantics.
- Add 135 reference-output cases and seeded live operator-combination checks,
  including independent expected answers and order-sensitive comparisons.

- Add Q8 joined-array expansion and composite grouping with reference and live
  weighting tests. Include all eight templates in the notebook workloads.

- Validate Q7 against corrected JSONBench and a live traveller-visit fixture.
  Add Q7 to the notebook workloads; no new translation operators are needed.

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
