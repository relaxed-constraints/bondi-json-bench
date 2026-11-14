# Testing

The commands assume an activated Python environment with the required packages
installed. Use `python -m venv .venv` or `uv venv .venv` to create one if needed;
see [Activate your Python environment](../quickstart.md#activate-your-python-environment).

Run checks from the repository root:

```sh
pytest
ruff check .
ruff format --check .
zensical build --strict
```

The default suite checks generation, reference translations, metrics, figures,
and CLI state transitions. GitHub CI runs this suite on Python 3.11–3.14, with
`JSONBENCH_LIVE=0`. It also checks formatting, generated CLI reference pages,
the documentation build, and installation of the built wheel.

Live database tests are opt-in and run locally with the command below. They do
not run automatically on GitHub.

```sh
JSONBENCH_LIVE=1 pytest tests/test_q5_live.py tests/test_q7_live.py \
  tests/test_q8_live.py tests/test_operator_combinations_live.py -q
```

Docker must be running. These tests create and remove disposable deployments.
They use ports 27137, 18391, 18393, and 21330. Run them sequentially and keep those
ports free. Inspect each test before changing its fixture or resource settings.

Passing translation fixtures establishes agreement with captured output. Live
comparisons check database behavior for the tested data. Neither is a proof for
all queries or documents.
