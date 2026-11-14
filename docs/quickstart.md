# Quickstart

This example runs a small functional check. It assumes a working development
checkout; the [installation page](installation.md) is still a placeholder.
Run these commands from the repository root. Start Docker first.

## Activate your Python environment

The command examples assume an activated Python environment with this project
and its dependencies installed.

If you need a new environment, create it with either command:

```sh
python -m venv .venv
```

Or, if you use uv:

```sh
uv venv .venv
```

Activate it on macOS or Linux:

```sh
source .venv/bin/activate
```

If your development checkout already has a `.venv`, activate that environment
instead of creating another one. See [Installation](installation.md) for the
status of the complete setup instructions.

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
  --warmup-seconds 2 --measurement-seconds 10 --drain-timeout-seconds 65
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
