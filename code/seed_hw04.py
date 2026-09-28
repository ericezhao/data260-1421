"""Seed 5,000 inspections and 200 violations for HW4 Part 3.

Uses SEED = 1421 so every run produces exactly the same rows.
Existing inspections and violations are wiped first; users and sessions are kept.

Run:  python seed_hw04.py
"""
import random

from sqlalchemy import text

import models
from database import Base, db_session_basede26, engine

SEED = 1421
NUM_INSPECTIONS = 5000
NUM_VIOLATIONS = 200

NAME_WORDS = [
    "Golden", "Lucky", "Sunny", "Blue", "Red", "Green", "Happy", "Little",
    "Royal", "Old Town", "Mission", "Bay", "Garden", "Silver", "Corner", "Harbor",
]
PLACE_TYPES = [
    "Cafe", "Kitchen", "Bistro", "Grill", "House", "Diner",
    "Noodle Bar", "Taqueria", "Bakery", "Sushi", "BBQ", "Eatery",
]
CUISINES = [
    "Japanese", "American", "French", "Mexican", "Italian",
    "Chinese", "Thai", "Indian", "Vietnamese", "Korean",
]
VIOLATIONS = [
    ("Cold food held above 41F", "critical"),
    ("Hot food held below 135F", "critical"),
    ("No hand washing between tasks", "critical"),
    ("Raw meat stored above ready-to-eat food", "major"),
    ("Food handler not wearing gloves", "major"),
    ("Evidence of pests in storage area", "major"),
    ("Sanitizer concentration too low", "major"),
    ("Food containers not labeled", "minor"),
    ("Floor under equipment not clean", "minor"),
    ("Employee drink in prep area", "minor"),
]


def main():
    rng = random.Random(SEED)
    Base.metadata.create_all(bind=engine)

    # TRUNCATE resets AUTO_INCREMENT so ids are 1..5000 on every run
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("TRUNCATE TABLE violations"))
        conn.execute(text("TRUNCATE TABLE inspections"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    db = db_session_basede26()
    try:
        inspections = [
            models.Inspection(
                restaurant_name=f"{rng.choice(NAME_WORDS)} {rng.choice(PLACE_TYPES)} #{i}",
                cuisine=rng.choice(CUISINES),
            )
            for i in range(1, NUM_INSPECTIONS + 1)
        ]
        db.add_all(inspections)
        db.flush()

        inspection_ids = [row.id for row in inspections]
        violations = []
        for _ in range(NUM_VIOLATIONS):
            description, severity = rng.choice(VIOLATIONS)
            violations.append(
                models.Violation(
                    inspection_id=rng.choice(inspection_ids),
                    description=description,
                    severity=severity,
                )
            )
        db.add_all(violations)
        db.commit()

        print(f"inspections: {db.query(models.Inspection).count()}")
        print(f"violations:  {db.query(models.Violation).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
