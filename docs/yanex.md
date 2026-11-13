# Advanced workflow with Yanex

Use Yanex when you need tracked experiments, dependency links, and flexible
result selection. Use the [CLI](cli.md) for a simple standalone matrix.
Both interfaces call the same [execution functions](experiments.md).

Run the following commands from the repository root.

## Prepare a dependency

```sh
uv run yanex run experiments/prepare.py   -c experiments/configs/prepare.yaml -p scale_factor=0.1 --tag exploration
```

The command prints an experiment ID. Preparation saves `preparation.json`, loads
both databases, creates indexes, and leaves the deployments stopped.

## Run one benchmark

Replace `<prepare-id>` with the ID from preparation:

```sh
uv run yanex run experiments/benchmark.py   -c experiments/configs/benchmark.yaml -D prepare=<prepare-id>   -p backend=mongodb -p clients=8 --tag exploration
```

The `prepare` dependency must have completed successfully. Dependencies identify
saved preparation results; they do not rerun preparation automatically.

## Sweep parameters

```sh
uv run yanex run experiments/benchmark.py   -c experiments/configs/benchmark.yaml -D prepare=<prepare-id>   -p 'backend=list(mongodb,couchbase)'   -p 'clients=list(2,4,8,16,32,64)' --tag exploration --stage
```

Inspect the staged experiments before executing them. Run them sequentially with
Yanex. Do not run several benchmarks against the same host concurrently. The
benchmark lock rejects overlap; it does not schedule waiting experiments.
`yanex run --staged` can include other staged work, so check that list first.

Each benchmark is one backend/client combination. To repeat a run, submit it
again and record the seed. To vary scale factor, create separate preparation
experiments and select their IDs as dependencies.

## Analyse a cohort

Open `notebooks/analysis.ipynb` in the checkout. Its first cell uses `yr.compare()`
to select completed experiments by project, script, and tag. Change the tag to
match your runs. Keep hardware, memory, workload, and timing settings consistent
within each comparison.

The notebook loads saved summaries and per-query samples, then calls the same
plotting functions as the CLI. CLI output folders are not Yanex experiments;
use `json-bench plot` for those folders.

## Configuration and cleanup

The YAML files keep deployment settings under `mongodb` and `couchbase`, and
benchmark timing under `load`. CLI flags do not change these YAML files.

Yanex preparation names deployments with its experiment ID. Inspect the saved
manifest before removing them with `bondi deployment remove <name>`.
`json-bench cleanup` manages CLI experiments, not Yanex experiment IDs.
