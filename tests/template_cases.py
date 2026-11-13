"""Seeded valid templates and small, deliberately varied documents for live checks."""

import random

DATA = {
    "tours": [
        {
            "_id": "a",
            "name": 'Alpha "quoted"',
            "difficulty": "easy",
            "score": 1,
            "details": {"rank": 1},
            "itinerary": [{"location": "X"}, {"location": "X"}],
        },
        {
            "_id": "b",
            "name": "Beta",
            "difficulty": "easy",
            "score": 3,
            "details": {"rank": 2},
            "itinerary": [{"location": "Y"}],
        },
        {
            "_id": "c",
            "name": "Gamma",
            "difficulty": "hard",
            "score": 8,
            "details": {"rank": 3},
            "itinerary": [],
        },
    ],
    "bookings": [
        {"_id": "b1", "tour_id": "a", "amount": 2},
        {"_id": "b2", "tour_id": "a", "amount": 4},
        {"_id": "b3", "tour_id": "b", "amount": 7},
        {"_id": "orphan", "tour_id": "missing", "amount": 9},
    ],
}


def generated_templates(seed=23, count=128):
    """Generate reproducible combinations; sorted keys identify unique rows/groups.

    Keep field types scalar and present. Nulls, mixed types and arbitrary query
    syntax are outside this compatibility check. The sequence is deduplicated.
    """
    if type(count) is not int or count < 0:
        raise ValueError("count must be a nonnegative integer")
    rng = random.Random(seed)
    seen = set()
    import json

    attempts = 0
    while len(seen) < count:
        attempts += 1
        if attempts > 100000:
            raise ValueError("Requested more unique templates than this generator can supply")
        ops = {}
        joined = rng.choice([True, False])
        expanded = rng.choice([True, False])
        if joined:
            ops["join"] = {"from": "bookings", "localField": "_id", "foreignField": "tour_id"}
        if expanded:
            ops["unnest"] = ["itinerary"]
        if rng.choice([True, False]):
            ops["match"] = {"difficulty": rng.choice(["easy", "hard", "absent"])}
        grouped = rng.choice([True, False])
        if grouped:
            # Each group has a unique source score, suitable for deterministic top-k.
            ops["group"] = {
                "by": "name",
                "aggregates": {"total": "sum(score)", "rank": "max(score)"},
            }
            sort_field = "rank"
        else:
            projection = {"name": 1, "details.rank": 1}
            if joined:
                projection["bookings._id"] = 1
            if expanded:
                projection["itinerary.location"] = 1
            if rng.choice([True, False]):
                ops["project"] = projection
            sort_field = "details.rank"
        # Joins and unnests introduce ties in ungrouped rows. Do not sort/limit those.
        if (grouped or not (joined or expanded)) and rng.choice([True, False]):
            ops["sort"] = {"field": sort_field, "direction": rng.choice([-1, 1])}
            if rng.choice([True, False]):
                ops["limit"] = rng.choice([1, 2, 4])
        encoded = json.dumps(ops, sort_keys=True)
        if encoded not in seen:
            seen.add(encoded)
            yield {"primary_collection": "tours", "operations": ops}


def named_templates():
    """Hand-written cases cover optional operators and independently known answers."""
    return [
        ("scan", {}, DATA["tours"]),
        ("quoted_filter", {"match": {"name": 'Alpha "quoted"'}}, DATA["tours"][:1]),
        ("projection", {"project": {"name": 1}}, [{"name": t["name"]} for t in DATA["tours"]]),
        (
            "top_two",
            {
                "project": {"name": 1, "details.rank": 1},
                "sort": {"field": "details.rank", "direction": -1},
                "limit": 2,
            },
            [{"name": "Gamma", "details_rank": 3}, {"name": "Beta", "details_rank": 2}],
        ),
        (
            "distinct",
            {"group": {"by": "difficulty", "aggregates": {}}},
            [{"difficulty": "easy"}, {"difficulty": "hard"}],
        ),
        (
            "group_top",
            {
                "group": {"by": "difficulty", "aggregates": {"total": "sum(score)"}},
                "sort": {"field": "total", "direction": -1},
                "limit": 1,
            },
            [{"difficulty": "hard", "total": 8}],
        ),
        ("empty", {"match": {"score": 99}}, []),
    ]
