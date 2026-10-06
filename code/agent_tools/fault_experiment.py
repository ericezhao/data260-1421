"""Part 3: 50 tool calls at 0%, 20% and 50% injected failure rates (150 calls), seeded with VERIFY_SEED.

Writes reports/hw05/raw/fault_injection_calls.csv (one row per call) and fault_injection_summary.csv.
"""

import csv
import hashlib
import logging
import math
import sys
import time
from pathlib import Path

from domain_tools import DEFAULT_POLICY, MySQLRepository, run_tool
from faults import FlakyRepository
from retry import Trace

logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)

VERIFY_SEED = 261421
RATES = [0.0, 0.2, 0.5]
CALLS_PER_RATE = 50
RAW = Path(__file__).resolve().parents[2] / "reports" / "hw05" / "raw"

WORKLOAD = [
    ("search_inspections", {"query": "Sushi", "limit": 5}),
    ("get_inspection", {"inspection_code": "INS-00042"}),
    ("score_summary", {"group_by": "cuisine", "top": 3}),
]


def p99(values: list[float]) -> float:
    """Nearest-rank 99th percentile: with 50 samples this is the slowest call."""
    ordered = sorted(values)
    return ordered[math.ceil(0.99 * len(ordered)) - 1]


def run_rate(real, rate: float) -> tuple[list[dict], str]:
    repo = FlakyRepository(real, rate, VERIFY_SEED)
    rows = []
    for i in range(CALLS_PER_RATE):
        tool, inputs = WORKLOAD[i % len(WORKLOAD)]
        trace = Trace()
        start = time.perf_counter()
        result = run_tool(tool, inputs, repo, DEFAULT_POLICY, trace)
        latency = (time.perf_counter() - start) * 1000
        rows.append(
            {
                "failure_rate": rate,
                "call": i + 1,
                "tool": tool,
                "attempts": len(trace.attempts),
                "attempt_outcomes": "|".join(a["outcome"].split(":")[0] for a in trace.attempts),
                "success": result["ok"],
                "latency_ms": round(latency, 2),
                "error": result["error"] or "",
            }
        )
    fingerprint = hashlib.sha256(",".join(repo.decisions).encode()).hexdigest()[:12]
    return rows, fingerprint


def main():
    print(f"Eric Zhao (SID4 1421) - fault injection, VERIFY_SEED={VERIFY_SEED}")
    p = DEFAULT_POLICY
    print(f"policy: max_attempts={p.max_attempts}, timeout={p.timeout_s}s, backoff={p.base_delay_s}s x2 (cap {p.max_delay_s}s)\n")
    real = MySQLRepository()
    real.get_by_code("INS-00001")  # warm up the connection pool so call 1 is not an outlier

    all_rows, summary = [], []
    for rate in RATES:
        rows, fingerprint = run_rate(real, rate)
        all_rows += rows
        latencies = [r["latency_ms"] for r in rows]
        successes = sum(r["success"] for r in rows)
        summary.append(
            {
                "failure_rate": f"{rate:.0%}",
                "calls": len(rows),
                "success_rate": f"{successes / len(rows):.0%}",
                "mean_latency_ms": round(sum(latencies) / len(latencies), 1),
                "p99_latency_ms": round(p99(latencies), 1),
                "mean_attempts": round(sum(r["attempts"] for r in rows) / len(rows), 2),
                "retried_calls": sum(r["attempts"] > 1 for r in rows),
                "failed_calls": len(rows) - successes,
                "decision_fingerprint": fingerprint,
            }
        )

    RAW.mkdir(parents=True, exist_ok=True)
    for name, data in [("fault_injection_calls.csv", all_rows), ("fault_injection_summary.csv", summary)]:
        with open(RAW / name, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)

    header = f"{'rate':>5} {'success':>8} {'mean ms':>9} {'p99 ms':>9} {'attempts':>9} {'retried':>8} {'failed':>7}  fingerprint"
    print(header)
    print("-" * len(header))
    for s in summary:
        print(
            f"{s['failure_rate']:>5} {s['success_rate']:>8} {s['mean_latency_ms']:>9} {s['p99_latency_ms']:>9} "
            f"{s['mean_attempts']:>9} {s['retried_calls']:>8} {s['failed_calls']:>7}  {s['decision_fingerprint']}"
        )
    print(f"\nsaved {len(all_rows)} call records to reports/hw05/raw/fault_injection_calls.csv")


if __name__ == "__main__":
    main()
