# BONDI JSON Bench


## Repository structure

| Directory | Purpose |
| --- | --- |
| `docs/` | Space for project notes and instructions. |
| `experiments/` | Thin Yanex adapters for shared experiment execution. |
| `experiments/configs/` | Preparation and benchmark parameters. |
| `notebooks/` | Future analysis notebooks. |
| `results/` | Use this directory to store experiment results and create progress update slides. |
| `src/json_bench/` | Core library for `bondi-json-bench`, including travel data generation, query translation, and analysis. |
| `tests/` | JSONBench compatibility and data-generation tests. |


## Setup

### 1. Open the local checkout

This repository is currently a local checkout. No new GitHub repository has been created:

```sh
cd ~/code/bondi-json-bench
```

### 2. Install dependencies and run tests

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from this directory:

#### Using `uv`:

```sh
uv sync --locked     # installs dependencies
uv run pytest        # runs the unit tests
uv run ruff check    # runs the linter to check code style
uv run ruff format   # formats the code according to the linter rules
```

#### Using `pip`:

In an activated Python virtual environment:

```sh
pip install -r requirements.txt
pytest        # runs the unit tests
ruff check    # runs the linter to check code style
ruff format   # formats the code according to the linter rules
```

See [Shared experiment execution](docs/experiments.md) for the preparation and
benchmark Python API used by both Yanex scripts.

## License

[MIT](LICENSE).

## Command-line benchmark

Use `json-bench prepare` and `json-bench benchmark` to run single combinations or
a full matrix without Yanex. See the [CLI guide](docs/cli.md) for commands,
settings, and resume behavior.

Use `json-bench cleanup --experiment <name>` to remove an experiment’s database
deployments and data after confirmation. Logs and result artifacts remain on disk.
