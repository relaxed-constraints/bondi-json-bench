# Testing

Run checks from the repository root:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run zensical build --strict
```

The default suite checks generation, reference translations, metrics, figures,
and CLI state transitions. Live database tests are opt-in.

```sh
JSONBENCH_LIVE=1 uv run pytest tests/test_q5_live.py tests/test_q7_live.py   tests/test_q8_live.py tests/test_operator_combinations_live.py -q
```

Docker must be running. These tests create and remove disposable deployments.
They use ports 27137, 18391, 18393, and 21330. Run them sequentially and keep those
ports free. Inspect each test before changing its fixture or resource settings.

Passing translation fixtures establishes agreement with captured output. Live
comparisons check database behavior for the tested data. Neither is a proof for
all queries or documents.
