# Benchmark design

The benchmark varies three main dimensions: data scale factor, database backend,
and concurrent clients. Repetitions let you inspect variation between runs.

## From data to observations

1. Generate the travel dataset with a fixed seed and reference date.
2. Load identical documents into MongoDB and Couchbase.
3. Create the [baseline indexes](indexes.md).
4. Translate the eight templates into native queries.
5. Run warm-up, measurement, and draining through BONDI.
6. Save each invocation and calculate run and query summaries.

The CLI and Yanex scripts call the same preparation and benchmark functions.
They differ in how they plan experiments and store tracking information.

## What the benchmark reveals

Throughput shows successful completions per measurement second. Runtime shows
how long successful queries take. Outcome charts show errors, timeouts, and
unresolved attempts. Read these together: a lower successful runtime can result
from slower queries timing out and leaving the successful sample.

Use the [metric definitions](analysis.md) when interpreting figures. Use the
[query descriptions](queries.md) to understand joins, array expansion, and weighting.
