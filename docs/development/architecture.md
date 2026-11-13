# Architecture

| Component | Responsibility |
| --- | --- |
| `data.py` | Generate travel documents without database or file access |
| `queries.py` | Validate templates and translate them into native BONDI queries |
| `validate.py` | Compare collected grouped query results |
| `indexes.py`, `deployment.py` | Apply benchmark-specific index and quota settings |
| `experiment.py` | Prepare databases and execute one benchmark run |
| `analysis.py` | Calculate measurement summaries and prepare result cohorts |
| `plotting.py` | Return Matplotlib figures from prepared analysis data |
| `cli.py` | Expand matrices, save state, resume, clean up, and export figures |
| `experiments/` | Yanex adapters, configuration, templates, and index definitions |

BONDI supplies deployments, document loading, query objects, executors, workloads,
and sustained-load generation. JSONBench owns the travel model, template language,
benchmark protocol, and analysis choices.

Both CLI and Yanex call `prepare_databases()` and `run_benchmark()`. Changes to
execution belong there, not in two separate interface implementations. Plotting
functions do not access databases or write files; callers choose how to save them.
