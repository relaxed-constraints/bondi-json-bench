# json-bench plot

Save notebook-style figures as PNG and PDF from completed run artifacts.

```sh
json-bench plot --experiment <name> [OPTIONS]
```

Use `--results-dir` when results are stored outside the default `results/` folder.

| Option | Description |
| --- | --- |
| `--experiment TEXT` | Name of the experiment to plot.  [required] |
| `--results-dir PATH` | [default: results] |
| `--dpi INTEGER RANGE` | PNG resolution.  [default: 200; x>=1] |
| `--help` | Show this message and exit. |

See the [CLI guide](../../cli.md) for examples and behavior.
