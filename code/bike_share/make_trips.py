"""Write two trip CSVs with at least 500 rows each."""

import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "hw07" / "raw" / "bike"


def write_trips(path: Path, n: int, duration_mean: float, seed: int) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trip_id",
                "week",
                "duration_min",
                "start_station",
                "member_casual",
            ],
        )
        writer.writeheader()
        for i in range(1, n + 1):
            duration = max(2.0, rng.gauss(duration_mean, max(1.0, duration_mean * 0.2)))
            writer.writerow(
                {
                    "trip_id": f"BW{i:05d}",
                    "week": 1 + (i % 4),
                    "duration_min": round(duration, 1),
                    "start_station": f"Station {rng.randint(1, 40)}",
                    "member_casual": "casual",
                }
            )


def main() -> None:
    write_trips(OUT / "membership_wins.csv", 520, duration_mean=28.0, seed=1421)
    write_trips(OUT / "payg_wins.csv", 520, duration_mean=3.0, seed=261421)
    print(f"wrote {OUT / 'membership_wins.csv'}")
    print(f"wrote {OUT / 'payg_wins.csv'}")


if __name__ == "__main__":
    main()
