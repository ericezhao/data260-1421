"""Run the two Bay Wheels scenarios and save snapshots/hashes."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from bike_share.make_trips import main as make_trips
from bike_share.pipeline import run_pipeline

RAW = ROOT / "reports" / "hw07" / "raw" / "bike"
LOG = ROOT / "reports" / "hw07" / "RUN_LOG.txt"
URL = "https://www.lyft.com/bikes/bay-wheels/pricing"


def save_snapshot(name: str, fixture_path: Path, result: dict) -> dict:
    text = fixture_path.read_text(encoding="utf-8")
    plain_hash = result["citations"]["sha256"]
    raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    out = RAW / f"{name}_snapshot.json"
    payload = {
        "scenario": name,
        "source_url": URL,
        "access_date": result["citations"]["accessed_at"],
        "sha256_extracted_text": plain_hash,
        "sha256_fixture_file": raw_hash,
        "fixture_file": str(fixture_path.relative_to(ROOT)),
        "decision": result["decision"],
        "metrics": result["metrics"],
        "cost_breakdown": result["cost_breakdown"],
        "justification": result["justification"],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (RAW / f"{name}_pricing_snapshot.html").write_text(text, encoding="utf-8")
    return payload


def main() -> None:
    make_trips()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Eric Zhao (SID4 1421) - Bay Wheels scenarios @ {stamp}")
    cases = [
        ("membership_wins", RAW / "membership_wins.csv", RAW / "baywheels_pricing_membership.html"),
        ("payg_wins", RAW / "payg_wins.csv", RAW / "baywheels_pricing_payg.html"),
    ]
    summaries = []
    for name, csv_path, fixture in cases:
        fixture_text = fixture.read_text(encoding="utf-8")
        result = run_pipeline(csv_path, pricing_url=URL, fixture_text=fixture_text)
        payload = save_snapshot(name, fixture, result)
        summaries.append(payload)
        print(
            f"{name}: decision={result['decision']} "
            f"payg={result['cost_breakdown']['pay_per_use_total']} "
            f"member={result['cost_breakdown']['membership_total']} "
            f"steps={result['metrics']['step_count']} "
            f"stop={result['metrics']['stop_reason']}"
        )
    (RAW / "bike_scenario_summary.json").write_text(
        json.dumps(summaries, indent=2) + "\n", encoding="utf-8"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{stamp}] part 4 bike scenarios\n")
        for item in summaries:
            handle.write(
                f"{item['scenario']}: {item['decision']} "
                f"sha256={item['sha256_extracted_text'][:12]} "
                f"stop={item['metrics']['stop_reason']}\n"
            )


if __name__ == "__main__":
    main()
