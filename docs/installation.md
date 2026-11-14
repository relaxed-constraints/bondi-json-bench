# Installation

Install BONDI JSON Bench from its GitHub repository. The checkout includes the
CLI, experiment definitions, notebooks, and documentation.

## Requirements

- Python 3.11 or newer.
- Git to clone the repository.
- Docker with Compose v2 to prepare and run database experiments.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) if you choose the uv instructions below.

Start Docker before running experiments. The default configuration allows each
database to use up to 24 GiB of memory. Docker needs enough memory for this cap
and other running containers. You can change the database memory settings with
[preparation options](reference/cli/prepare.md).

You do not need Docker to install the project or plot saved results.

## Clone the repository

```sh
git clone https://github.com/relaxed-constraints/bondi-json-bench.git
cd bondi-json-bench
```

## Create an environment and install

Choose either uv or pip. Run these commands from the repository root.

=== "uv"

    ```sh
    uv venv .venv
    uv sync --locked
    source .venv/bin/activate
    ```

    `uv sync --locked` installs the project and its dependencies from `uv.lock`.
    It also installs the development tools.

=== "pip"

    ```sh
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e .
    ```

    pip reads the dependencies from `pyproject.toml`; no `requirements.txt` is
    needed. The editable installation uses the source in this checkout. pip
    resolves compatible dependency versions rather than using `uv.lock`.

On Windows PowerShell, replace `source .venv/bin/activate` with
`.venv\Scripts\Activate.ps1`.

Both options install published BONDI 0.3.1 with MongoDB and Couchbase support.
A separate BONDI checkout is not needed.

## Check the installation

With the environment activated, run:

```sh
json-bench --help
```

The help output lists `prepare`, `benchmark`, `plot`, and `cleanup`.
The command examples in this documentation assume an activated environment,
so you do not need to prefix them with `uv run`.

Continue with the [quickstart](quickstart.md) to prepare a small dataset,
run both databases, and plot the results.
