# Part 2: at least 10 queries (exact, paraphrase, new)
import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.query_handler import CachedQA
from hw09.semantic_cache import SemanticResponseCache

OUT = ROOT / "reports" / "hw09" / "raw" / "part2_results.json"

QUERIES = [
    "Why do inspection scores matter for sushi restaurants?",
    "Why do inspection scores matter for sushi restaurants?",  # exact dup
    "Why should sushi places care about their inspection score?",  # paraphrase
    "What is the inspection score range used in this system?",
    "What numbers can an inspection score be between?",  # paraphrase
    "How are critical violations different from noncritical ones?",
    "What's the difference between critical and non-critical violations?",
    "How do I reset my bike share PIN?",  # unrelated / new
    "What cuisine tends to get more temperature violations?",
    "Which type of restaurant often fails hot/cold holding checks?",
    "Explain how TCP differs from UDP.",  # new
    "Does a closed placard mean the restaurant failed inspection?",
]


def main():
    print("Eric Zhao SID4=1421 Part2 semantic cache")
    cache = SemanticResponseCache(threshold=0.85)
    cache.clear()
    cache.set_data_version(1)
    qa = CachedQA(threshold=0.85, cache=cache)

    rows = []
    for q in QUERIES:
        rows.append(qa.ask(q))

    hits = [r for r in rows if r["is_cached"]]
    misses = [r for r in rows if not r["is_cached"]]
    summary = {
        "n": len(rows),
        "hits": len(hits),
        "misses": len(misses),
        "hit_rate_pct": round(100.0 * len(hits) / len(rows), 1),
        "avg_latency_cached_ms": round(mean(r["latency_ms"] for r in hits), 2) if hits else None,
        "avg_latency_uncached_ms": round(mean(r["latency_ms"] for r in misses), 2)
        if misses
        else None,
        "threshold": 0.85,
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
