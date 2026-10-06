import random
from sqlalchemy import text
import models
from database import Base, db_session_basede26, engine

SEED = 1421
NUM_INSPECTIONS = 5000
NUM_VIOLATIONS = 200
NUM_OWNERS = 50

FIRST_NAMES = [
    "Maria", "Kevin", "Aisha", "Daniel", "Grace", "Robert", "Emily", "James",
    "Sofia", "Minh", "Priya", "Carlos", "Hannah", "Wei", "Olivia", "Jorge",
]
LAST_NAMES = [
    "Lopez", "Tran", "Patel", "Kim", "Chen", "Silva", "Nguyen", "Carter",
    "Garcia", "Wong", "Shah", "Rivera", "Park", "Liu", "Brooks", "Ramos",
]
DEDUCTION = {"critical": 8, "major": 3, "minor": 2}

NAME_WORDS = [
    "Golden", "Lucky", "Sunny", "Blue", "Red", "Green", "Happy", "Little",
    "Royal", "Old Town", "Mission", "Bay", "Garden", "Silver", "Corner", "Harbor",
]
PLACE_TYPES = [
    "Cafe", "Kitchen", "Bistro", "Grill", "House", "Diner",
    "Noodle Bar", "Taqueria", "Bakery", "Sushi", "BBQ", "Eatery",
]
CUISINES = [
    "Japanese", "New American", "French", "Mexican", "Italian",
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


def make_owners(rng):
    pairs = rng.sample([(f, l) for f in FIRST_NAMES for l in LAST_NAMES], NUM_OWNERS)
    return [
        models.Owner(
            name=f"{first} {last}",
            phone=f"408-{rng.randint(200, 999)}-{rng.randint(0, 9999):04d}",
            email=f"{first.lower()}.{last.lower()}@example.com",
        )
        for first, last in pairs
    ]


def main():
    rng = random.Random(SEED)
    # separate generator so names, cuisines and violations match the HW4 data
    owner_rng = random.Random(SEED)

    # drop and recreate so the tables always match models.py; ids restart at 1
    with engine.begin() as conn:
        conn.execute(text("SET SESSION lock_wait_timeout = 10"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("DROP TABLE IF EXISTS violations, inspections, owners"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    Base.metadata.create_all(bind=engine)

    db = db_session_basede26()
    try:
        owners = make_owners(owner_rng)
        db.add_all(owners)
        db.flush()
        owner_ids = [row.id for row in owners]

        inspections = [
            models.Inspection(
                restaurant_name=f"{rng.choice(NAME_WORDS)} {rng.choice(PLACE_TYPES)} #{i}",
                cuisine=rng.choice(CUISINES),
                inspection_code=f"INS-{i:05d}",
                score=100,
                owner_id=owner_rng.choice(owner_ids),
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

        by_id = {row.id: row for row in inspections}
        for v in violations:
            by_id[v.inspection_id].score -= DEDUCTION[v.severity]
        db.commit()

        print(f"owners:      {db.query(models.Owner).count()}")
        print(f"inspections: {db.query(models.Inspection).count()}")
        print(f"violations:  {db.query(models.Violation).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
