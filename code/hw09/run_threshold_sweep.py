# Part 3.2 threshold sweep over cache_cases.yaml
import json
import sys
from pathlib import Path
from statistics import mean

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.config import FALSE_HIT_COST, MISS_COST
from hw09.query_handler import CachedQA
from hw09.semantic_cache import SemanticResponseCache

CASES = Path(__file__).with_name("cache_cases.yaml")
OUT = ROOT / "reports" / "hw09" / "raw" / "threshold_sweep.json"


def load_cases():
    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    return data["cases"]


def run_at_threshold(cases, threshold):
    cache = SemanticResponseCache(threshold=threshold)
    cache.clear()
    cache.set_data_version(1)
    qa = CachedQA(threshold=threshold, cache=cache)

    seeded = set()
    rows = []
    for case in cases:
        seed = case.get("seed_query") or case["query"]
        if seed not in seeded:
            # warm cache with seed (counts as a miss write, not scored)
            qa.ask(seed, threshold=threshold)
            seeded.add(seed)
        # scored ask
        if case["query"] == seed and case["category"] == "exact":
            # ask again for exact duplicate
            got = qa.ask(case["query"], threshold=threshold)
        else:
            got = qa.ask(case["query"], threshold=threshold)
        expected = bool(case["expected_hit"])
        actual = bool(got["is_cached"])
        false_hit = actual and not expected
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected_hit": expected,
                "is_cached": actual,
                "false_hit": false_hit,
                "similarity": got["similarity"],
                "latency_ms": got["latency_ms"],
                "query": case["query"],
                "seed_query": seed,
                "answer": got["answer"],
            }
        )

    n = len(rows)
    hits = sum(1 for r in rows if r["is_cached"])
    false_hits = sum(1 for r in rows if r["false_hit"])
    hit_rate = hits / n
    false_hit_rate = false_hits / n
    # cost: misses pay MISS_COST, false hits pay FALSE_HIT_COST
    misses = n - hits
    total_cost = misses * MISS_COST + false_hits * FALSE_HIT_COST
    return {
        "threshold": threshold,
        "n": n,
        "hit_rate": round(hit_rate, 4),
        "false_hit_rate": round(false_hit_rate, 4),
        "mean_latency_ms": round(mean(r["latency_ms"] for r in rows), 2),
        "total_cost": round(total_cost, 4),
        "miss_cost": MISS_COST,
        "false_hit_cost": FALSE_HIT_COST,
        "rows": rows,
    }


def main():
    print("Eric Zhao SID4=1421 Part3 threshold sweep")
    cases = load_cases()
    assert len(cases) == 40, len(cases)
    thresholds = [0.75, 0.80, 0.85, 0.90, 0.95]
    results = [run_at_threshold(cases, t) for t in thresholds]

    # pick shipped threshold = lowest total cost, break ties by lower false-hit
    best = sorted(results, key=lambda r: (r["total_cost"], r["false_hit_rate"]))[0]

    # prefer a false hit at the default 0.85 threshold (e.g. F02), else first
    false_example = None
    ordered = sorted(results, key=lambda r: (0 if abs(r["threshold"] - 0.85) < 1e-9 else 1))
    for block in ordered:
        for row in block["rows"]:
            if row["false_hit"]:
                false_example = {
                    "threshold": block["threshold"],
                    "incoming_query": row["query"],
                    "cached_query": row["seed_query"],
                    "similarity": row["similarity"],
                    "cached_answer": row["answer"],
                    "correct_answer": (
                        "A miss: answer the incoming question on its own entity "
                        "(e.g. Mexican vs Japanese), do not reuse the cached "
                        "cuisine-specific answer."
                    ),
                    "why_confused": (
                        "Embeddings cluster shared template words "
                        "('cuisine', 'high risk', 'raw fish') so different "
                        "cuisine slots still look close."
                    ),
                }
                break
        if false_example:
            break

    payload = {
        "table": [
            {
                "threshold": r["threshold"],
                "hit_rate": r["hit_rate"],
                "false_hit_rate": r["false_hit_rate"],
                "mean_latency_ms": r["mean_latency_ms"],
                "total_cost": r["total_cost"],
            }
            for r in results
        ],
        "chosen_threshold": best["threshold"],
        "chosen_reason": (
            f"lowest total_cost={best['total_cost']} with "
            f"false_hit_rate={best['false_hit_rate']}"
        ),
        "false_hit_example": false_example,
        "details": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["table"], indent=2))
    print("chosen=", payload["chosen_threshold"], payload["chosen_reason"])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
