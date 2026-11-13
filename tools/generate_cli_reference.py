"""Generate CLI option tables from Click without maintaining duplicate defaults."""

import argparse
from pathlib import Path

import click

from json_bench.cli import main


def render(name, command):
    """Return one reference page using the command's current help records."""
    context = click.Context(command, info_name=f"json-bench {name}")
    rows = []
    for parameter in command.get_params(context):
        record = parameter.get_help_record(context)
        if record:
            option, description = record
            description = description.replace("|", "\\|")
            rows.append(f"| `{option}` | {description} |")
    return (
        f"# json-bench {name}\n\n{command.help}\n\n"
        f"```sh\njson-bench {name} --experiment <name> [OPTIONS]\n```\n\n"
        "Use `--results-dir` when results are stored outside the default `results/` folder.\n\n"
        "| Option | Description |\n| --- | --- |\n"
        + "\n".join(rows)
        + "\n\nSee the [CLI guide](../../cli.md) for examples and behavior.\n"
    )


def generate():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "docs/reference/cli"
    destination.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, command in main.commands.items():
        path = destination / f"{name}.md"
        text = render(name, command)
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path))
        else:
            path.write_text(text)
    if stale:
        parser.exit(1, "Regenerate CLI reference pages:\n" + "\n".join(stale) + "\n")


if __name__ == "__main__":
    generate()
