# Add a query or operator

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

## Explore in the notebook

`notebooks/walkthrough.ipynb` demonstrates generation, loading, translation,
validation, and sustained load. Use small scale factors while developing. Check
its final deployment lifecycle cell before running it; retained data and removed
data have different effects on the next run.
