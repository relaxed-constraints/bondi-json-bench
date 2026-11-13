# json-bench prepare

Create a stopped MongoDB/Couchbase pair for each scale factor.

```sh
json-bench prepare --experiment <name> [OPTIONS]
```

Use `--results-dir` when results are stored outside the default `results/` folder.

| Option | Description |
| --- | --- |
| `--experiment TEXT` | Name chosen for this experiment.  [required] |
| `--results-dir PATH` | [default: results] |
| `--dry-run` | Show the plan without writing files or starting databases. |
| `--resume` | Skip completed combinations and retry unfinished ones. |
| `--scale-factor TEXT` | Comma-separated scale factors.  [default: 0.1] |
| `--seed INTEGER` | [default: 23] |
| `--reference-date TEXT` | [default: 2025-11-01] |
| `--mongodb-version TEXT` | [default: 8.2.1] |
| `--couchbase-version TEXT` | [default: 8.0.0] |
| `--memory-limit-mb INTEGER RANGE` | [default: 24576; x>=1] |
| `--mongodb-cache-gb FLOAT RANGE` | [default: 12; x>0] |
| `--couchbase-data-mb INTEGER RANGE` | [default: 8192; x>=1] |
| `--couchbase-index-mb INTEGER RANGE` | [default: 4096; x>=1] |
| `--mongodb-port INTEGER RANGE` | [default: 27147; 1<=x<=65535] |
| `--couchbase-management-port INTEGER RANGE` | [default: 18491; 1<=x<=65535] |
| `--couchbase-query-port INTEGER RANGE` | [default: 18493; 1<=x<=65535] |
| `--couchbase-kv-port INTEGER RANGE` | [default: 21430; 1<=x<=65535] |
| `--help` | Show this message and exit. |

See the [CLI guide](../../cli.md) for examples and behavior.
