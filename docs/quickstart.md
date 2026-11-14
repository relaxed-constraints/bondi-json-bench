# Quickstart

This example runs a small functional check. First follow the
[installation instructions](installation.md).

Run these commands from the repository root after installing dependencies and activating your Python environment. Start Docker first.

## Prepare a small dataset

```sh
json-bench prepare --experiment quickstart --scale-factor 0.1
```

Preparation creates MongoDB and Couchbase deployments, loads the same documents,
and creates baseline indexes. Both databases stop when preparation finishes.
The default memory cap is 24 GiB per database. Docker must have enough memory
available; use the [preparation options](reference/cli/prepare.md) to change it.

## Run both backends

```sh
json-bench benchmark --experiment quickstart --clients 2 \
  --warmup-seconds 5 --measurement-seconds 30 --drain-timeout-seconds 15
```

The databases run one at a time. These short timings test the workflow; they are
not suitable for drawing performance conclusions.

## Plot the saved results

```sh
json-bench plot --experiment quickstart
```

PNG and PDF files appear in `results/quickstart/figures/`. The command uses saved
artifacts and does not start a database.

## Remove the database data

```sh
json-bench cleanup --experiment quickstart
```

Review the listed names and confirm removal. Logs, query observations, and
figures remain in the experiment folder. Use a new experiment name for another
preparation after cleanup.

Next, use the [CLI guide](cli.md) to run the full matrix or resume an interrupted run.
