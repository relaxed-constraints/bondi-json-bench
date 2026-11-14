# Run the benchmark from the command line

`json-bench` prepares travel data and benchmarks MongoDB and Couchbase without
Yanex. BONDI manages the local Docker deployments. Start Docker before running
preparation. These examples assume an activated Python environment with the
project installed. Create an environment with `python -m venv .venv` or
`uv venv .venv`, then activate it as shown in the
[quickstart](quickstart.md#activate-your-python-environment).

## Run one combination

A single run consists of a combination of scale factor (specified during preparation), backend, and client count (both specified during benchmarking).

Choose an experiment name (here `my-run`). The CLI saves data preparation details and results
under `results/<experiment>/`.

First, prepare the database deployments, datasets and indexes:
```sh
json-bench prepare --experiment my-run --scale-factor 10
```

Then, using the same experiment name, run the benchmark:
```sh
json-bench benchmark --experiment my-run --backend mongodb --clients 8
```

Preparation creates one MongoDB/Couchbase pair for the chosen scale factor. It loads
the same generated documents into both databases, creates the baseline indexes,
and stops both databases. Data volumes remain available for benchmarks.


## Run the full matrix

Specify comma-separated values for scale factors, backends, and client counts to run the full matrix.

```sh
json-bench prepare --experiment my-run --scale-factor 10,100,200

json-bench benchmark --experiment my-run \
  --backend mongodb,couchbase --clients 2,4,8,16,32,64 --repetitions 3
```

This runs 108 combinations: three scale factors, two backends, six client counts,
and three repetitions. Benchmarks use all prepared scale factors unless you
supply `--scale-factor` in the benchmark command.

Runs execute sequentially: backend, scale factor, repetition, then client count.
Only the selected database runs during each measurement. The CLI stops it after
that run. Repetition 1 uses a default random seed `23` by default, later repetitions increment the
seed. Each combination records its effective seed and settings.

CLI operations share a host lock to prevent concurrent access to the same
database deployments from different benchmarks.

## Preview and resume

Add `--dry-run` to either command to show its planned combinations without
starting databases or writing result files. Benchmark preview requires completed
preparation so it can resolve available scale factors.

If a `benchmark` command fails or is interrupted, repeat it with `--resume`:

```sh
json-bench benchmark --experiment my-run \
  --backend mongodb,couchbase --clients 2,4,8,16,32,64 --repetitions 3 --resume
```

Resume skips completed combinations. Earlier observations and error details remain on
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

### Preparation Settings

Preparation defaults are set to these values:

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
18491/18493/21430 for Couchbase management/query/KV.

### Benchmark Settings

Benchmark defaults:

| Setting | Default | Option |
| --- | --- | --- |
| Scale factors | All prepared scale factors | `--scale-factor` |
| Backends | MongoDB and Couchbase | `--backend` |
| Concurrent clients | 2 | `--clients` |
| Repetitions | 1 | `--repetitions` |
| Selection seed | 23; increments for each repetition | `--seed` |
| Warm-up duration | 60 seconds | `--warmup-seconds` |
| Measurement duration | 180 seconds | `--measurement-seconds` |
| Maximum drain duration | 60 seconds | `--drain-timeout-seconds` |
| Query timeout | 60 seconds | `--timeout-seconds` |
| Health-check timeout | 60 seconds | `--health-check-timeout-seconds` |
| Database startup timeout | 300 seconds | `--startup-timeout-seconds` |
| Q1–Q8 selection weights | `1,1,1,1,1,1,1,1` | `--weights` |
| Q4 location | `Donnafurt` | `--q4-location` |

`--weights` takes eight nonnegative numbers in Q1–Q8 order. The default gives each
query equal weight. For example, `--weights 3,1,1,1,1,1,1,1` selects Q1 three times
as often as each other template in expectation. `--q4-location` defaults to
`Donnafurt`. Templates and index definitions are included with the installed
package and copied into the experiment state.

## Saved results

```text
results/my-run/
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
json-bench cleanup --experiment my-run
```

Use the same `--results-dir` as preparation if you changed its default. Cleanup
lists the deployment names and asks for confirmation. It removes their containers
and data volumes, including deployments recorded in failed preparation attempts.
It does not delete logs, observations, summaries, or other artifacts. It adds a
cleanup record to `state.json`.

Use `--dry-run` to preview removal or `--yes` to skip confirmation. Missing
deployments are harmless. If removal fails partway through, run cleanup again.

Once cleanup starts, this experiment cannot resume preparation or benchmarks.
Choose a new experiment name to prepare new datasets. Saved results remain
available for analysis.

## Generate figures

```sh
json-bench plot --experiment my-run
```

Use the same `--results-dir` as preparation and benchmarking. The command reads
completed run artifacts and writes PNG and PDF files under
`results/my-run/figures/`. It does not start databases or change run results,
and it still works after cleanup. PNG files use 200 DPI by default; use `--dpi`
to change the resolution.

The figures match the analysis notebook:

- `clients_by_scale`: throughput and mean successful runtime against client count.
- `query_outcomes_normalized`: success, error, timeout, and unresolved percentages.
- `failure_heatmaps`: error plus timeout percentages by scale factor and client count.
- `query_runtimes_sf-*` and `query_runtimes_all`: successful runtime distributions by query.
- `query_outcomes_sf-*` and `query_outcomes_all`: outcome counts by query.

Scale factors, client counts, and repetitions come from the saved runs. The
per-query figures pool client counts, as in the notebook. Completed runs with
query errors or timeouts remain included. Failed, interrupted, or pending runs
are listed as skipped. Missing or inconsistent artifacts in a completed run
cause an error rather than silent exclusion.

`plot_manifest.json` records the included attempt paths, skipped runs, output
filenames, and DPI. Re-running the command overwrites matching figure filenames.
It does not delete other files in the figures folder. Use the manifest to identify
the files produced by the latest plot command.
