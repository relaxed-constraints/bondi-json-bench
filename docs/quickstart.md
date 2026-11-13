# Quickstart

This example runs a small functional check. It assumes a working development
checkout; the [installation page](installation.md) is still a placeholder.
Run these commands from the repository root. Start Docker first.

## Prepare a small dataset

```sh
uv run json-bench prepare --experiment quickstart --scale-factor 0.1
```

Preparation creates MongoDB and Couchbase deployments, loads the same documents,
and creates baseline indexes. Both databases stop when preparation finishes.
The default memory cap is 24 GiB per database. Docker must have enough memory
available; use the [preparation options](reference/cli/prepare.md) to change it.

## Run both backends

```sh
uv run json-bench benchmark --experiment quickstart --clients 2   --warmup-seconds 2 --measurement-seconds 10 --drain-timeout-seconds 65
```

The databases run one at a time. These short timings test the workflow; they are
not suitable for drawing performance conclusions.

## Plot the saved results

```sh
uv run json-bench plot --experiment quickstart
```

PNG and PDF files appear in `results/quickstart/figures/`. The command uses saved
artifacts and does not start a database.

## Remove the database data

```sh
uv run json-bench cleanup --experiment quickstart
```

Review the listed names and confirm removal. Logs, query observations, and
figures remain in the experiment folder. Use a new experiment name for another
preparation after cleanup.

Next, use the [CLI guide](cli.md) to run the full matrix or resume an interrupted run.
