# Extending the benchmark

## Change a template

Templates live in `experiments/templates/`. Load one with `load_template(path)`,
then translate it for both backends. Run it on a small dataset and inspect the
collected results before measuring performance.

The current runner expects exactly Q1–Q8. Replacing a template is different from
adding a ninth query: the latter also requires changes to labels, weights, and
runner validation. Use a new experiment when workload semantics change.

## Add an operator

1. Specify its input syntax and execution order.
2. Define how MongoDB and Couchbase should execute it.
3. Add translation tests for accepted and rejected inputs.
4. Add a small fixture with independently known answers.
5. Run the paired live checks, including operator combinations.
6. Update the template guide and API documentation.

Reject unsupported cases with clear errors. Do not silently approximate a query.
Be explicit about nulls, missing fields, duplicate rows, and join multiplicity.

## Investigate performance differences

Use the benchmark to investigate why MongoDB and Couchbase perform differently
for a workload. A throughput or runtime gap is a starting point for investigation;
it does not, by itself, identify the bottleneck.

Start with one query template and a small scale factor. Inspect the query plan
and collect execution statistics from each database. Check where time is spent:
scanning indexes, fetching documents, expanding arrays, joining collections, or
aggregating results. Compare these observations with CPU, memory, and disk use.
For example, investigate whether a slow Couchbase query fetches many documents
or repeatedly scans a collection during a join.

Useful extensions include:

- **Secondary indexes:** test indexes that match filter and join fields. Where
  supported, explore covering indexes or array indexes. Check whether the query
  plan uses them and record their storage and preparation costs.
- **Query translations:** explore alternative native query forms that let each
  database execute the same template more efficiently. Preserve filters, grouping,
  duplicate rows, and join multiplicity. Use reference cases and live result
  comparisons to check that an optimisation preserves the answers.
- **Resource and execution settings:** investigate cache allocations, query
  parallelism, and resource limits. Record database versions and editions, since
  available features and limits can differ.

Change one factor at a time and keep the baseline results. Use separate experiment
names or Yanex runs for each variant, with the same dataset, workload weights,
client counts, and timing settings. Repeat measurements and report errors and
timeouts alongside successful query runtimes. A lower mean runtime can result
from slow queries failing rather than completing faster.

After a promising result on a small dataset, test larger scale factors and higher
client counts. Report tuned configurations separately from the baseline, and give
both databases a comparable opportunity for tuning. The aim is to explain which
workload features expose a limitation and whether a specific change addresses it.

## Explore in the notebook

`notebooks/walkthrough.ipynb` demonstrates generation, loading, translation,
validation, and sustained load. Use small scale factors while developing. Check
its final deployment lifecycle cell before running it; retained data and removed
data have different effects on the next run.
