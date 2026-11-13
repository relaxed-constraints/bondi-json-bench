# json-bench cleanup

Remove recorded deployments and data volumes; keep all result files.

```sh
json-bench cleanup --experiment <name> [OPTIONS]
```

Use `--results-dir` when results are stored outside the default `results/` folder.

| Option | Description |
| --- | --- |
| `--experiment TEXT` | Name of the experiment to clean up.  [required] |
| `--results-dir PATH` | [default: results] |
| `--dry-run` | List recorded deployments without removing them. |
| `-y, --yes` | Skip the confirmation prompt. |
| `--help` | Show this message and exit. |

See the [CLI guide](../../cli.md) for examples and behavior.
