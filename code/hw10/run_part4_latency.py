#!/usr/bin/env python3
# Part 4.3: 50 confirmed cache misses (mock llm for speed, like hw8 timing)
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

os.environ.setdefault("HW10_MOCK_LLM", "1")
os.environ.setdefault("HW8_MOCK_LLM", "1")
os.environ.setdefault("HW10_MOCK_JUDGE", "1")

from hw10.evaluator import evaluate_artifact
from hw10.latency import analyze_miss_traces
from hw10.pipeline import handle_request


def main():
    n = int(os.getenv("HW10_LATENCY_N", "50"))
    tids = []
    for i in range(n):
        q = f"HW10 latency miss #{i} seed={uuid.uuid4().hex} what is a critical violation?"
        tid = f"lat{i:02d}-{uuid.uuid4().hex[:8]}"
        print(f"[latency] {i+1}/{n} {tid}")
        handle_request(q, trace_id=tid, force_miss=True, skip_cache_store=True)
        try:
            evaluate_artifact(tid, mock=True)
        except Exception as e:
            print("[latency] eval warn", tid, e)
        tids.append(tid)

    result = analyze_miss_traces(tids)
    print("verified", result["n_verified_cache_miss"], "e2e_p50", result["e2e_p50_ms"])
    print(result.get("optimize_first"))
    for row in result["stages"]:
        print(
            row["stage"],
            "p50=",
            row["p50_ms"],
            "p95=",
            row["p95_ms"],
            "%",
            row["pct_of_cache_miss_e2e"],
        )
    return 0 if result["n_verified_cache_miss"] >= n else 1


if __name__ == "__main__":
    raise SystemExit(main())
