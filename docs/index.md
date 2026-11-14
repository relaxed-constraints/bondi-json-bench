# BONDI JSON Bench

**Generate analytical workloads based on query templates and benchmark them against MongoDB and Couchbase. Understand how their behavior changes with data size and concurrency.**

BONDI JSON Bench rebuilds the [JSONBench](https://github.com/zeNightshade/JSONBench) benchmark on the [BONDI](https://relaxed-constraints.github.io/bondi/) document database research toolkit and the [Yanex](https://relaxed-constraints.github.io/yanex/) experiment management framework.

It generates travel data, translates query templates to MongoDB and Couchbase backends, runs sustained workloads, and produces figures from saved results.

!!! abstract "Attribution"
    This project is based on the Honours theses of **Zenwei Lee** and **Chester Li**, supervised by [Assoc. Prof. Uwe Roehm](https://profiles.sydney.edu.au/uwe.roehm) at the University of Sydney, School of Computer Science, Databases group.

## The workflow

**Prepare → Benchmark → Plot → Cleanup**

Prepare one dataset per scale factor. Run each database separately, then compare
throughput, successful query runtimes, and outcomes. Cleanup removes database
containers and volumes while preserving result files.

The CLI is the recommended entry point. The Yanex scripts use the same execution
functions and add experiment tracking, dependencies, and parameter sweeps.

## Choose your starting point

| Your goal | Start here |
| --- | --- |
| Review the benchmark | [Benchmark design](design.md) and [Results](results.md) |
| Run an experiment | [Quickstart](quickstart.md) and [CLI guide](cli.md) |
| Explore a research question | [Yanex workflow](yanex.md) |
| Add a query or operator | [Extension guide](development/extending.md) |
| Call the library from Python | [API reference](reference/index.md) |

## The paper

This project builds on *JSONBench: Benchmarking JSON Document Stores for Analytical
Workloads*, by Zenwei Lee, Thomas Rueckstiess, and Uwe Roehm, submitted to ICDE 2027
on 11 November 2026.

The submitted paper used the earlier JSONBench implementation. Results from this
BONDI-based implementation are a separate reproduction. The [Results](results.md)
page will identify the code, settings, and runs used for its figures.

## Scope

The benchmark includes a synthetic travel dataset and eight analytical query
templates. It also supports additional combinations of the template operators.
Read the [validation limits](validation.md) before extending the templates or data types.
