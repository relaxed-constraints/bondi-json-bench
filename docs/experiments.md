# Shared experiment execution

`json_bench.experiment` runs preparation and benchmarks without importing Yanex.
The scripts in `experiments/` supply Yanex parameters, dependencies and output callbacks.
No CLI is included yet.

## Prepare databases

```python
from json_bench.experiment import prepare_databases

prepared = prepare_databases(
    preparation_params,
    run_id="my-preparation",
    indexes=index_definitions,
    output_dir="results/my-preparation",
)
```

`preparation_params` uses the complete structure in `experiments/configs/prepare.yaml`.
`index_definitions` uses `experiments/indexes.json`. Callers load these inputs;
the library does not depend on paths inside a checkout.

The function generates one dataset and loads each backend in sequence. It uses
replacement loads and creates the baseline indexes. It then stops each database,
keeping its data. `run_id` supplies the deployment-name suffix. Choose a new ID
for a new preparation; reusing it can replace data in those deployments.

The returned dictionary is the existing `preparation.json` manifest. Its
`experiment_id` field holds the supplied run ID, even without Yanex.
Failures save a failed manifest, retain partial data, and propagate the error.

## Run a benchmark

```python
from json_bench.experiment import run_benchmark

analysis = run_benchmark(
    prepared,
    benchmark_params,
    scale_factor=preparation_params["scale_factor"],
    templates=templates,  # Q1 through Q8, in order
    output_dir="results/mongodb-8",
)
```

`benchmark_params` uses `experiments/configs/benchmark.yaml`. No defaults are
added by the shared functions. Supply the scale factor from preparation because
older preparation manifests do not contain it.

The function stops both prepared databases, starts the selected backend, and
calls BONDI's `generate_load()`. It preserves query weights, phase durations,
query timeouts and measurement rules. It stops the selected database on exit.
The return value is the existing `LoadAnalysis` with run and per-query summaries.

A host lock prevents overlapping benchmark calls. Preparation does not take
this lock, so run preparation separately. The lock does not control other programs.

## Outputs and callbacks

Both functions write JSON artifacts into `output_dir` by default. Each benchmark
also flushes individual observations to `load_results.jsonl` during execution.
Use a separate output directory for each run; existing artifact files are overwritten.

Optional callbacks let another interface handle reporting:

- `on_progress(message)` receives progress text. The default prints immediately.
- `on_artifact(value, filename)` replaces the JSON artifact writer. It must save
  the value synchronously and must not mutate it. JSONL streaming still writes
  directly into `output_dir`.
- `on_metrics(metrics)` receives the scalar metric dictionary.
- `run_benchmark(..., on_result=callback)` passes each BONDI `LoadResult` to the
  callback after writing its JSONL record. Treat the observation as read-only.

Callback exceptions propagate. Early termination writes summaries and metrics
before raising an error. Already written observations remain available.
Yanex passes `save_artifact` and `log_metrics` as callbacks, preserving the
existing artifact names and formats. A plain Python caller can omit them.

## Individual steps

`load_dataset(deployment, dataset, *, on_progress=...)` replaces the travel
collections and checks acknowledged write counts. It does not start or stop the
supplied deployment.

`create_indexes(deployment, indexes, *, on_progress=...)` creates the baseline
indexes and closes its native client. Supply the index mapping for that backend.
Both functions require a running deployment and propagate errors.
