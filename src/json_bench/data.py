"""Generate travel documents with the original JSONBench distributions."""

import math
import random
from datetime import date, timedelta

from faker import Faker


def generate_travel_dataset(
    *, scale: float, seed: int, reference_date: str
) -> dict[str, list[dict]]:
    """Generate users, tours, bookings and reviews in memory.

    Args:
        scale: Finite scale factor of at least 0.01. Collection sizes are
            int(scale * N), with N = 1000, 200, 5000 and 2500 respectively.
        seed: Seed for fresh Python and Faker random generators.
        reference_date: ISO date (YYYY-MM-DD) used as the date reference.

    Returns:
        Four lists keyed by users, tours, bookings and reviews. Dates are ISO
        strings and IDs are the original JSONBench string IDs.

    Raises:
        ValueError: Invalid scale factor or reference date.

    Generation preserves JSONBench's random calls, order and distributions.
    Identical inputs produce identical documents with the same dependency
    versions. All documents are held in memory. No files or databases are used.
    """
    generator = _TravelGenerator(seed=seed, reference_date=reference_date)
    dataset: dict[str, list[dict]] = {"users": [], "tours": [], "bookings": [], "reviews": []}
    for collection, record in generator.records(scale):
        dataset[collection].append(record)
    return dataset


class _TravelGenerator:
    def __init__(self, *, seed, reference_date):
        self.rng = random.Random(seed)
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.reference = date.fromisoformat(reference_date)
        self.seed = seed

    def records(self, scale):
        if (
            isinstance(scale, bool)
            or not isinstance(scale, (int, float))
            or not math.isfinite(scale)
            or scale < 0.01
        ):
            raise ValueError("Scale factor must be finite and at least 0.01")
        # A fresh instance is used for every public function call.
        users, guides, tours, bookings = [], [], [], []
        fake, rng = self.fake, self.rng
        count = int(1000 * scale)
        for index in range(count):
            identity = f"user-{index}"
            role = "guide" if index >= int(count * 0.9) else "user"
            (guides if role == "guide" else users).append(identity)
            yield (
                "users",
                {
                    "_id": identity,
                    "name": fake.name(),
                    "email": fake.email(),
                    "password": fake.password(16),
                    "role": role,
                    "gender": rng.choice(["F", "M", "X"]),
                    "nationality": fake.country(),
                },
            )
        for index in range(int(200 * scale)):
            duration = rng.randint(1, 31)
            start = self.reference - timedelta(days=rng.randint(duration, 3650))
            itinerary, day = [], 0
            while day < duration:
                itinerary.append(
                    {"location": fake.city(), "date": (start + timedelta(days=day)).isoformat()}
                )
                day += rng.randint(1, max(1, duration // 4))
            tour = {
                "_id": f"tour-{index}",
                "name": fake.name(),
                "description": fake.text(500),
                "difficulty": rng.choices(["easy", "intermediate", "hard"], [0.5, 0.35, 0.15])[0],
                "duration": duration,
                "max_group_size": rng.randint(10, 100),
                "rrp": round(rng.uniform(100, 10000), 2),
                "departure": fake.country(),
                "destination": fake.country(),
                "itinerary": itinerary,
                "guide_id": rng.choice(guides),
            }
            tours.append((tour["_id"], tour["rrp"]))
            yield "tours", tour
        for index in range(int(5000 * scale)):
            tour, price = rng.choice(tours)
            travellers = [
                {
                    "name": fake.name(),
                    "age": rng.randint(1, 100),
                    "gender": rng.choice(["F", "M", "X"]),
                    "nationality": fake.country(),
                }
                for _ in range(rng.randint(1, 10))
            ]
            when = self.reference - timedelta(days=rng.randint(1, 3650))
            identity = f"booking-{index}"
            bookings.append((identity, tour, when))
            yield (
                "bookings",
                {
                    "_id": identity,
                    "user_id": rng.choice(users),
                    "tour_id": tour,
                    "travellers": travellers,
                    "total_price": round(price * len(travellers), 2),
                    "date": when.isoformat(),
                    "paid": rng.random() < 0.8,
                    "travelled": rng.random() < 0.75,
                },
            )
        for index in range(int(2500 * scale)):
            booking, tour, when = rng.choice(bookings)
            review_date = when + timedelta(days=rng.randint(1, (self.reference - when).days))
            yield (
                "reviews",
                {
                    "_id": f"review-{index}",
                    "booking_id": booking,
                    "tour_id": tour,
                    "rating": rng.randint(1, 5),
                    "review": fake.text(2000),
                    "date": review_date.isoformat(),
                },
            )
