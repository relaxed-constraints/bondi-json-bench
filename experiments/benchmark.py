"""Run one backend/client combination against a prepared Yanex dependency."""

from pathlib import Path

import yanex

from json_bench.experiment import run_benchmark
from json_bench.queries import load_template


def main():
    prepare = yanex.get_dependency("prepare")
    if prepare is None:
        raise ValueError("Supply a preparation experiment with -D prepare=<experiment-id>")
    manifest = prepare.load_artifact("preparation.json")
    if prepare.status != "completed" or not manifest or manifest.get("status") != "ready":
        raise ValueError("The prepare dependency must have completed database preparation")

    template_dir = Path(__file__).with_name("templates")
    run_benchmark(
        manifest,
        yanex.get_params(),
        scale_factor=prepare.get_param("scale_factor"),
        templates=[load_template(template_dir / f"q{i}.json") for i in range(1, 9)],
        output_dir=yanex.get_artifacts_dir(),
        on_artifact=yanex.save_artifact,
        on_metrics=yanex.log_metrics,
    )


if __name__ == "__main__":
    main()
