"""Prepare two stopped, populated databases for dependent Yanex experiments."""

import json
from pathlib import Path

import yanex

from json_bench.experiment import prepare_databases


def main():
    params = yanex.get_params()
    indexes = json.loads(Path(__file__).with_name("indexes.json").read_text())
    prepare_databases(
        params,
        run_id=yanex.get_experiment_id(),
        indexes=indexes,
        output_dir=yanex.get_artifacts_dir(),
        on_artifact=yanex.save_artifact,
        on_metrics=yanex.log_metrics,
    )


if __name__ == "__main__":
    main()
