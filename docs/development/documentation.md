# Build the documentation

Zensical and the Python API renderer are core dependencies. From the checkout:

```sh
uv run python tools/generate_cli_reference.py
uv run zensical build --strict
uv run zensical serve --dev-addr 127.0.0.1:8001
```

Open the address printed by Zensical. Generated site files live in `site/` and
are not committed. This repository has no automatic publishing workflow yet.

Edit navigation and theme settings in `zensical.toml`. Edit prose under `docs/`.
API pages read docstrings from `src/json_bench/`. CLI reference pages are generated
from Click command definitions; update them after changing options or defaults.
Use `--check` on the reference generator to detect stale pages.

Use short sentences, active verbs, and concrete examples. Keep metric definitions
in the benchmark-design section and link to them from guides. Keep installation
and results marked as placeholders until their instructions and evidence are ready.
