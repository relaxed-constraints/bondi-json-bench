"""File loading and experiment-template compatibility."""

import json
from pathlib import Path

import pytest

from json_bench.queries import load_template, translate_couchbase, translate_mongodb

ROOT = Path(__file__).resolve().parents[1]


def test_load_string_path_and_fresh_objects(tmp_path):
    path = tmp_path / "template.json"
    path.write_text('{"name": "Café", "operations": {}}', encoding="utf-8")
    first = load_template(str(path))
    assert first == {"name": "Café", "operations": {}}
    first["operations"]["changed"] = True
    assert load_template(path)["operations"] == {}


@pytest.mark.parametrize("value", [[], None, "text", 1, True])
def test_requires_object(tmp_path, value):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="must contain a JSON object") as exc:
        load_template(path)
    assert str(path) in str(exc.value)


def test_file_and_json_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_template(tmp_path / "missing.json")
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(json.JSONDecodeError):
        load_template(path)


def test_loader_does_not_validate_operations(tmp_path):
    path = tmp_path / "custom.json"
    path.write_text('{"operations": {"future_operator": {}}}')
    assert "future_operator" in load_template(path)["operations"]


@pytest.mark.parametrize("number", range(1, 9))
def test_paper_templates_match_independent_references(number):
    template = load_template(ROOT / "experiments/templates" / f"q{number}.json")
    reference = json.loads((ROOT / "tests/fixtures" / f"q{number}_translation.json").read_text())
    assert template == reference["template"]
    assert translate_mongodb(template, database="travel").pipeline == reference["mongodb_pipeline"]
    assert (
        translate_couchbase(template, bucket="travel").statement == reference["couchbase_statement"]
    )


@pytest.mark.parametrize("directory", [ROOT, ROOT / "notebooks"])
def test_notebook_builds_workloads_from_both_directories(directory, monkeypatch):
    notebook = json.loads((ROOT / "notebooks/walkthrough.ipynb").read_text())
    cell = next(c for c in notebook["cells"] if c.get("id") == "q1-translation")
    monkeypatch.chdir(directory)
    namespace = {"dataset": {"tours": [{"itinerary": [{"location": "Test City"}]}]}}
    exec("".join(cell["source"]), namespace)
    assert len(namespace["mongo_workload"]) == len(namespace["couchbase_workload"]) == 8
    assert namespace["templates"][3]["operations"]["match"]["itinerary.location"] == "Test City"
    assert (
        load_template(ROOT / "experiments/templates/q4.json")["operations"]["match"][
            "itinerary.location"
        ]
        == "Donnafurt"
    )
