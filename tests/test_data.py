"""Travel generation matches independently captured JSONBench output."""

import hashlib
import json
import random
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from json_bench.data import generate_travel_dataset

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "travel_compatibility.json").read_text()
)


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_matches_original_jsonbench(case):
    data = generate_travel_dataset(**case["inputs"])
    assert list(data) == ["users", "tours", "bookings", "reviews"]
    for collection, expected in case["collections"].items():
        documents = data[collection]
        assert len(documents) == expected["count"]
        digest = hashlib.sha256(
            json.dumps(documents, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        assert digest == expected["sha256"], collection


def test_reproducible_fresh_results_and_random_isolation():
    args = dict(scale=0.01, seed=23, reference_date="2025-11-01")
    state = random.getstate()
    first = generate_travel_dataset(**args)
    assert random.getstate() == state
    first["users"][0]["name"] = "changed"
    second = generate_travel_dataset(**args)
    assert second == generate_travel_dataset(**args)
    assert first != second
    assert second != generate_travel_dataset(**{**args, "seed": 24})


def test_relationships_and_original_rules():
    data = generate_travel_dataset(scale=0.01, seed=23, reference_date="2025-11-01")
    users = {row["_id"]: row for row in data["users"]}
    tours = {row["_id"]: row for row in data["tours"]}
    bookings = {row["_id"]: row for row in data["bookings"]}
    assert Counter(row["role"] for row in users.values()) == {"user": 9, "guide": 1}
    for collection, rows in data.items():
        prefix = {"users": "user", "tours": "tour", "bookings": "booking", "reviews": "review"}[
            collection
        ]
        assert [row["_id"] for row in rows] == [f"{prefix}-{i}" for i in range(len(rows))]
    for tour in tours.values():
        assert users[tour["guide_id"]]["role"] == "guide"
        assert tour["difficulty"] in {"easy", "intermediate", "hard"}
        assert 1 <= tour["duration"] <= 31
        dates = [date.fromisoformat(stop["date"]) for stop in tour["itinerary"]]
        assert dates == sorted(set(dates))
    for booking in bookings.values():
        assert users[booking["user_id"]]["role"] == "user"
        assert 1 <= len(booking["travellers"]) <= 10
        assert booking["total_price"] == round(
            tours[booking["tour_id"]]["rrp"] * len(booking["travellers"]), 2
        )
    for review in data["reviews"]:
        booking = bookings[review["booking_id"]]
        assert review["tour_id"] == booking["tour_id"]
        assert booking["date"] < review["date"] <= "2025-11-01"
        assert 1 <= review["rating"] <= 5


@pytest.mark.parametrize(
    "scale", [True, False, None, "1", 0, -1, 0.009, float("nan"), float("inf"), -float("inf")]
)
def test_invalid_scale(scale):
    with pytest.raises(ValueError, match="Scale factor"):
        generate_travel_dataset(scale=scale, seed=23, reference_date="2025-11-01")


def test_invalid_reference_date():
    with pytest.raises(ValueError):
        generate_travel_dataset(scale=0.01, seed=23, reference_date="not-a-date")
