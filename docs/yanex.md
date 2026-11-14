# Advanced workflow with Yanex

The commands assume an activated Python environment with the required packages
installed. Use `python -m venv .venv` or `uv venv .venv` to create one if needed;
see [Create an environment and install](installation.md#create-an-environment-and-install).

Use [Yanex](https://relaxed-constraints.github.io/yanex) for exploratory analysis when you need tracked experiments, dependency links, and flexible
result selection. Use the [CLI](cli.md) for a simple standalone matrix.
Both interfaces call the same [execution functions](experiments.md).

Run the following commands from the `experiments` directory.

## Prepare a dependency

```sh
yanex run prepare.py \
  -c configs/prepare.yaml -p scale_factor=0.1 -n "my-prepare-sf-{scale_factor}"
```

This will create an experiment with the name `my-prepare-sf-0.1`, overriding the default scale factor with `0.1`. All defaults can be found under `experiments/configs/prepare.yaml`.


You can also add a description (`--description` / `-d`) or tags (`--tag` / `-t`) to organise your experiments. See the [`yanex run` documentation](https://relaxed-constraints.github.io/yanex) for more details.


The command prints an experiment ID, record it as your `<prepare-id>`. Preparation saves `preparation.json` to the experiment folder, loads both databases, creates indexes, and leaves the deployments stopped.

#### Other useful yanex commands in this context

- `yanex list` lists all experiments for this projects
- `yanex show <prepare-id>` shows details for a specific experiment, including its dependencies and status.
- `yanex open <prepare-id>` opens the experiment folder in the default file browser.
- `yanex delete <prepare-id>` deletes an experiment and its associated files.

See a full list of available CLI commands in the [Yanex CLI Reference](https://relaxed-constraints.github.io/yanex/cli/).



## Run one benchmark

Replace `<prepare-id>` with the ID from preparation above:

```sh
yanex run benchmark.py \
  -c configs/benchmark.yaml -D prepare=<prepare-id> \
  -p backend=mongodb -p clients=8 --name "my-benchmark-{backend}-{clients}"
```

This creates a benchmark experiment named `my-benchmark-mongodb-8` based on the provided parameters. Other `yanex run` arguments are available as discussed above.

The `-D` (short for `--depends-on`) flag links the current benchmark experiment to the specified prepare experiment and creates a dependency. This gives the benchmark access to the results of the preparation step. The `prepare` dependency must have completed successfully.

## Sweep parameters

Yanex allows to run multiple experiments with different parameter combinations using parameter sweeps.

```sh
yanex run benchmark.py \
  -c configs/benchmark.yaml -D prepare=<prepare-id> \
  -p backend=mongodb,couchbase -p clients=2,4,8,16,32,64 \
  --name "my-benchmark-{backend}-{clients}"
```

As the benchmark measures throughput, do not use Yanex's `--parallel` flag. The
default behavior is to run experiments sequentially.

Each benchmark is one backend/client combination. To repeat a run, sweep over
the `seed` parameter with an additional list of seeds, e.g. `-p seed=23,24,25`.
This executes the benchmark for each combination of backend, client count, and seed specified.

## Analyse a cohort

Open `notebooks/analysis.ipynb`. Its first cell uses `yr.compare()`
to select completed experiments by various filtering criteria, e.g. project, script, status, name and tags. Change these to match your desired cohort of runs.

Keep hardware, memory, workload, and timing settings consistent within each comparison.

The notebook loads saved summaries and per-query samples, then calls the same
plotting functions as the CLI.

## Configuration and cleanup

Yanex preparation names deployments with its `prepare` experiment ID. Inspect the saved
manifest or use `bondi deployment list` before removing them with `bondi deployment remove <name>`.
