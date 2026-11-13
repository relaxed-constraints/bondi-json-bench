# Run the benchmark from the command line

`json-bench` prepares travel data and benchmarks MongoDB and Couchbase without
Yanex. BONDI manages the local Docker deployments. Start Docker before running
preparation. Install the project with `uv sync`, then prefix the commands below
with `uv run` when using the checkout.

## Run one combination

Choose an experiment name. The CLI saves data preparation details and results
under `results/<experiment>/`.

```sh
json-bench prepare --experiment my-run --scale-factor 10
json-bench benchmark --experiment my-run --backend mongodb --clients 8
```

Preparation creates one MongoDB/Couchbase pair for each scale factor. It loads
the same generated documents into both databases, creates the baseline indexes,
and stops both databases. Data volumes remain available for benchmarks.

## Run the full matrix

```sh
json-bench prepare --experiment paper-run --scale-factor 10,100,200
json-bench benchmark --experiment paper-run \
  --backend mongodb,couchbase --clients 2,4,8,16,32,64 --repetitions 3
```

This runs 108 combinations: three scale factors, two backends, six client counts,
and three repetitions. Benchmarks use all prepared scale factors unless you
supply `--scale-factor`. Each command accepts a single value or a comma-separated
list for its matrix dimensions.

Runs execute sequentially: backend, scale factor, repetition, then client count.
Only the selected database runs during each measurement. The CLI stops it after
that run. Repetition 1 uses seed 23 by default; later repetitions increment the
seed. Each combination records its effective seed and settings.

Stop unrelated database workloads before measurement. These commands do not stop
unrelated deployments. CLI operations share a host lock. Preparation also checks
the shared benchmark lock, so it cannot overlap a Yanex benchmark. Yanex
preparation scripts do not acquire this lock; do not run them concurrently.

## Preview and resume

Add `--dry-run` to either command to show its planned combinations without
starting databases or writing result files. Benchmark preview requires completed
preparation so it can resolve available scale factors.

If a command fails or is interrupted, repeat it with `--resume`:

```sh
json-bench benchmark --experiment paper-run \
  --backend mongodb,couchbase --clients 2,4,8,16,32,64 --repetitions 3 --resume
```

Resume skips completed combinations. Query errors and timeouts are benchmark
outcomes: a completed run containing them is not retried. A failed or interrupted
run gets a new attempt folder. Earlier observations and error details remain on
disk. The command stops at the first infrastructure or execution failure. Resolve
its cause before resuming. Do not resume while an earlier process is still running.

You can add client counts, backends, or repetitions with `--resume`. You can also
select a subset of prepared scale factors. Timing, query weights, seed, and other
benchmark settings must remain unchanged. Use a new experiment for a new protocol.
Preparation resume requires the same scale factors and preparation settings.
It skips completed scale factors and reloads an unfinished dataset pair.

## Settings

Use `json-bench prepare --help` and `json-bench benchmark --help` for all options.
There is no configuration-file interface. Both commands accept `--results-dir`
(default `results`). Use the same directory and experiment name in both commands.

Preparation defaults match the current Yanex preparation settings:

| Setting | Default | Option |
| --- | --- | --- |
| Scale factor | 0.1 | `--scale-factor` |
| Dataset seed | 23 | `--seed` |
| Reference date | 2025-11-01 | `--reference-date` |
| MongoDB version | 8.2.1 | `--mongodb-version` |
| Couchbase Community version | 8.0.0 | `--couchbase-version` |
| Total memory cap, per database | 24576 MiB | `--memory-limit-mb` |
| WiredTiger cache | 12 GiB | `--mongodb-cache-gb` |
| Couchbase data quota | 8192 MiB | `--couchbase-data-mb` |
| Couchbase index quota | 4096 MiB | `--couchbase-index-mb` |

Docker needs enough memory for these allocations and service overhead. Port
options are available for both backends. The defaults are 27147 for MongoDB and
18491/18493/21430 for Couchbase management/query/KV. Each dataset pair reuses these
ports because pairs run sequentially. Do not start several pairs together.

Benchmark defaults are two clients, both backends, one repetition, 60 seconds of
warm-up, 180 seconds of measurement, and up to 60 seconds of draining. Query and
health-check timeouts are 60 seconds. Startup has a separate 300-second timeout.
Use `--warmup-seconds`, `--measurement-seconds`, `--drain-timeout-seconds`,
`--timeout-seconds`, `--health-check-timeout-seconds`, and
`--startup-timeout-seconds` to change them.

`--weights` takes eight nonnegative numbers in Q1–Q8 order. The default gives each
query equal weight. For example, `--weights 3,1,1,1,1,1,1,1` selects Q1 three times
as often as each other template in expectation. `--q4-location` defaults to
`Donnafurt`. Templates and index definitions are included with the installed
package and copied into the experiment state.

## Saved results

```text
results/paper-run/
  state.json
  preparations/sf-10/attempt-1/
    params.json
    preparation.json
    indexes.json
  runs/mongodb-sf-10-clients-2-rep-1/attempt-1/
    params.json
    benchmark.json
    templates.json
    queries.json
    load_results.jsonl
    summary.json
    per_query.json
```

`state.json` records the plans, resolved settings, attempt paths, and completion
status. Each failed attempt also contains `error.txt`. Keep this file and the
result folders together. Do not edit state to mark runs complete.

The CLI uses the same [shared execution functions](experiments.md) as Yanex.
The metric definitions and result file formats are unchanged. CLI results are
ordinary files; they are not registered as Yanex experiments.

## Remove database deployments

When you no longer need the database data, run:

```sh
json-bench cleanup --experiment paper-run
```

Use the same `--results-dir` as preparation if you changed its default. Cleanup
lists the deployment names and asks for confirmation. It removes their containers
and data volumes, including deployments recorded in failed preparation attempts.
It does not delete logs, observations, summaries, or other artifacts. It adds a
cleanup record to `state.json`.

Use `--dry-run` to preview removal or `--yes` to skip confirmation. Missing
deployments are harmless. If removal fails partway through, run cleanup again.
The command uses the CLI and benchmark locks to reject concurrent operations.

Once cleanup starts, this experiment cannot resume preparation or benchmarks.
Choose a new experiment name to prepare new datasets. Saved results remain
available for analysis. Moving result files to another host does not move the
Docker deployments.
