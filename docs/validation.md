# Query equivalence checks

We check translation compatibility and execution results separately.

## Reference-output tests

The test fixtures contain MongoDB pipelines and Couchbase SQL++ captured from
the JSONBench implementation. Tests compare generated queries against
these fixtures, including destination metadata. The fixtures record the source
revision and checksums. No old JSONBench checkout is needed to run them.

Q1–Q8 each have a reference fixture. Another fixture covers 135 operator
combinations: seven hand-written cases and 128 generated templates with seed 23.
These tests detect changes to translation output. They do not execute databases.

## Live comparisons

Live tests load controlled documents into both databases and execute paired
queries. Some cases have independently specified expected answers. Others compare
the two result sets after normalizing known differences in their output shapes.

For grouped queries, `compare_results()` maps MongoDB's `_id` group keys to
Couchbase's named fields. It checks keys exactly and numeric aggregates with
relative tolerance `1e-9` and absolute tolerance `1e-6`. Duplicate groups fail.
Unsorted groups may appear in any order. Sorted results must agree in order;
use unique sort keys to avoid ambiguous ties.

The operator-combination live tests also cover ungrouped results. Their test
helpers preserve duplicates and normalize the native output shapes. The public
`compare_results()` helper only supports grouped templates.

## Limits

The fixtures use known arrays and scalar join keys. Missing values, nulls, mixed
types, and malformed documents need separate tests. A finite set of templates
cannot prove equivalence for every possible template and dataset.

See [Testing](development/testing.md) for commands and the
[validation API](reference/validation.md) for the public helper.
