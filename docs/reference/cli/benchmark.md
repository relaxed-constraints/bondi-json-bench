# json-bench benchmark

Run combinations sequentially against prepared databases.

```sh
json-bench benchmark --experiment <name> [OPTIONS]
```

Use `--results-dir` when results are stored outside the default `results/` folder.

| Option | Description |
| --- | --- |
| `--experiment TEXT` | Name chosen for this experiment.  [required] |
| `--results-dir PATH` | [default: results] |
| `--dry-run` | Show the plan without writing files or starting databases. |
| `--resume` | Skip completed combinations and retry unfinished ones. |
| `--scale-factor TEXT` | Comma-separated subset; defaults to all prepared scales. |
| `--backend TEXT` | [default: mongodb,couchbase] |
| `--clients TEXT` | Comma-separated client counts.  [default: 2] |
| `--repetitions INTEGER RANGE` | [default: 1; x>=1] |
| `--seed INTEGER` | [default: 23] |
| `--warmup-seconds FLOAT RANGE` | [default: 60; x>=0] |
| `--measurement-seconds FLOAT RANGE` | [default: 180; x>0] |
| `--drain-timeout-seconds FLOAT RANGE` | [default: 60; x>=0] |
| `--timeout-seconds FLOAT RANGE` | [default: 60; x>0] |
| `--health-check-timeout-seconds FLOAT RANGE` | [default: 60; x>0] |
| `--startup-timeout-seconds FLOAT RANGE` | [default: 300; x>0] |
| `--weights TEXT` | Q1–Q8 selection weights.  [default: 1,1,1,1,1,1,1,1] |
| `--q4-location TEXT` | [default: Donnafurt] |
| `--help` | Show this message and exit. |

See the [CLI guide](../../cli.md) for examples and behavior.
