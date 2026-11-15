# Build the documentation

The commands assume an activated Python environment with the required packages
installed. Use `python -m venv .venv` or `uv venv .venv` to create one if needed;
see [Create an environment and install](../installation.md#create-an-environment-and-install).

Install the documentation dependency group from the checkout with
`uv sync --locked --group docs` (or `python -m pip install --group docs`).
Then run:

```sh
python tools/generate_cli_reference.py
zensical build --strict
zensical serve --dev-addr 127.0.0.1:8001
```

Open the address printed by Zensical. Generated site files live in `site/` and
are not committed. Pull requests check the documentation with a strict build.
Changes pushed to `main` deploy the site to GitHub Pages after CI passes.
You can also run the Documentation workflow manually from GitHub Actions.

Edit navigation and theme settings in `mkdocs.yml`. Edit prose under `docs/`.
API pages read docstrings from `src/json_bench/`. CLI reference pages are generated
from Click command definitions; update them after changing options or defaults.
Use `--check` on the reference generator to detect stale pages.

Use short sentences, active verbs, and concrete examples. Keep metric definitions
in the benchmark-design section and link to them from guides. Keep results marked as a placeholder until the evidence is ready.

## Shared configuration

The pinned relcon-docs package supplies the theme, light/dark diagram and copy
button styling, Markdown exports, llms.txt, callouts and equation rendering.
MathJax loads from jsDelivr only on pages with equations. The local results.css
retains the benchmark figure layout.

To upgrade, update the Git commit in pyproject.toml, run `uv lock` and
`uv sync --locked --group docs`, then run:

```sh
relcon-docs configure --dry-run
relcon-docs configure
relcon-docs configure --check
zensical build --strict
```

Keep project overrides in mkdocs.yml. Do not edit managed files under
.relcon-docs/, docs/stylesheets/relcon-docs.css or
docs/javascripts/relcon-docs-math.js. Configuration updates detect local edits;
review conflicts before using --force. Update the reusable workflow commit in
.github/workflows/docs.yml separately; its main/manual triggers are project-owned.
