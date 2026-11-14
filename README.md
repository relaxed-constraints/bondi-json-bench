# BONDI JSON Bench

An analytical document database benchmark built on BONDI. Generate travel data,
run MongoDB and Couchbase workloads, and compare throughput, runtimes, and outcomes.

The CLI runs individual combinations or a sequential matrix. Yanex scripts support
tracked research experiments using the same execution functions.

## Documentation

Start with the [documentation home](https://relaxed-constraints.github.io/bondi-json-bench/) or [quickstart](docs/quickstart.md).
Follow the [installation guide](docs/installation.md) to set up a checkout with
uv or pip. Evaluation results remain a placeholder while the full matrix is prepared.

| Goal | Guide |
| --- | --- |
| Run the CLI | [CLI workflow](docs/cli.md) |
| Track experiments with Yanex | [Yanex workflow](docs/yanex.md) |
| Understand the benchmark | [Benchmark design](docs/design.md) |
| Use Python functions | [API reference](docs/reference/index.md) |
| Extend the project | [Development](docs/development/index.md) |

Preview the site from an existing development checkout with its Python environment
activated and dependencies installed. You can create an environment with
`python -m venv .venv` or `uv venv .venv`; see the
[activation instructions](docs/quickstart.md#activate-your-python-environment).

```sh
zensical serve --dev-addr 127.0.0.1:8001
```

See [Build the documentation](docs/development/documentation.md) for reference
page generation and strict checks.

## Repository structure

| Directory | Purpose |
| --- | --- |
| `src/json_bench/` | Generation, translation, execution, analysis, plotting, and CLI |
| `experiments/` | Yanex scripts, configuration, templates, and indexes |
| `notebooks/` | Walkthrough and cohort analysis |
| `tests/` | Unit, compatibility, and optional live tests |
| `docs/` | Zensical documentation source |
| `results/` | Local CLI outputs, excluded from Git |

## License

[MIT](LICENSE).
