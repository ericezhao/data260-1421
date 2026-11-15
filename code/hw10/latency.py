# part 4.3 p50/p95 for confirmed cache-miss traces
import json
import statistics

from hw10.config import LATENCY_JSON, REPORTS_DIR
from hw10.tracing import SpanStore

STAGES = ["cache_lookup", "planner", "writer", "reviewer", "queue_wait", "eval"]


def _pct(vals, p):
    if not vals:
        return None
    xs = sorted(vals)
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return round(xs[f], 3)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 3)


def analyze_miss_traces(trace_ids, span_store=None):
    store = span_store or SpanStore()
    per_stage = {s: [] for s in STAGES}
    e2e = []
    verified = []

    for tid in trace_ids:
        spans = store.load(tid)
        if not spans:
            continue
        cl = next((s for s in spans if s.get("stage") == "cache_lookup"), None)
        if not cl or cl.get("cache_hit") or cl.get("status") == "error":
            continue
        verified.append(tid)
        by = {s["stage"]: s for s in spans}
        total = 0.0
        for stage in STAGES:
            if stage == "queue_wait":
                q = 0.0
                if "planner" in by:
                    q = by["planner"].get("queue_wait_ms", 0.0) or 0.0
                if "queue_wait" in by:
                    q = by["queue_wait"].get("duration_ms", q)
                per_stage["queue_wait"].append(float(q))
                total += float(q)
                continue
            if stage in by and "duration_ms" in by[stage]:
                d = float(by[stage]["duration_ms"])
                per_stage[stage].append(d)
                total += d
        e2e.append(total)

    rows = []
    e2e_p50 = _pct(e2e, 50) or 1.0
    for stage in STAGES:
        vals = per_stage[stage]
        p50 = _pct(vals, 50)
        p95 = _pct(vals, 95)
        mean = statistics.mean(vals) if vals else None
        rows.append(
            {
                "stage": stage,
                "n": len(vals),
                "p50_ms": p50,
                "p95_ms": p95,
                "mean_ms": round(mean, 3) if mean is not None else None,
                "pct_of_cache_miss_e2e": round(100.0 * (p50 or 0) / e2e_p50, 2),
            }
        )

    dominant = max(rows, key=lambda r: r["p50_ms"] or 0) if rows else None
    out = {
        "n_requested": len(trace_ids),
        "n_verified_cache_miss": len(verified),
        "trace_ids": verified,
        "e2e_p50_ms": _pct(e2e, 50),
        "e2e_p95_ms": _pct(e2e, 95),
        "stages": rows,
        "dominant_stage": dominant,
        "optimize_first": (
            f"Optimize {dominant['stage']} first (p50={dominant['p50_ms']} ms)."
            if dominant
            else None
        ),
    }
    LATENCY_JSON.parent.mkdir(parents=True, exist_ok=True)
    LATENCY_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    labels = {
        "cache_lookup": "Cache lookup",
        "planner": "Planner",
        "writer": "Writer",
        "reviewer": "Reviewer",
        "queue_wait": "Queue wait (total)",
        "eval": "Evaluation",
    }
    lines = [
        "| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {labels[r['stage']]} | {r['p50_ms']} | {r['p95_ms']} | "
            f"{r['pct_of_cache_miss_e2e']} |"
        )
    (REPORTS_DIR / "latency_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
