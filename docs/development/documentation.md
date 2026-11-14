# Build the documentation

The commands assume an activated Python environment with the required packages
installed. Use `python -m venv .venv` or `uv venv .venv` to create one if needed;
see [Activate your Python environment](../quickstart.md#activate-your-python-environment).

Zensical and the Python API renderer are core dependencies. From the checkout:

```sh
python tools/generate_cli_reference.py
zensical build --strict
zensical serve --dev-addr 127.0.0.1:8001
```

Open the address printed by Zensical. Generated site files live in `site/` and
are not committed. Pull requests check the documentation with a strict build.
Changes pushed to `main` deploy the site to GitHub Pages after CI passes.
You can also run the Documentation workflow manually from GitHub Actions.

Edit navigation and theme settings in `zensical.toml`. Edit prose under `docs/`.
API pages read docstrings from `src/json_bench/`. CLI reference pages are generated
from Click command definitions; update them after changing options or defaults.
Use `--check` on the reference generator to detect stale pages.

Use short sentences, active verbs, and concrete examples. Keep metric definitions
in the benchmark-design section and link to them from guides. Keep installation
and results marked as placeholders until their instructions and evidence are ready.
