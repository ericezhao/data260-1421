# summary metrics for streamlit page
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from hw10.config import MESSAGES_DIR, SPANS_DIR, SUMMARY_JSON, TRACE_INDEX_JSON
from hw10.tracing import SpanStore


def _percentile(vals, p):
    if not vals:
        return None
    xs = sorted(vals)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def load_all_spans(root=None):
    store = SpanStore(root=root)
    rows = []
    for tid in store.list_trace_ids():
        rows.extend(store.load(tid))
    return rows


def build_summary(span_root=None, message_root=None):
    spans = load_all_spans(span_root)
    msg_root = Path(message_root) if message_root else MESSAGES_DIR
    messages = []
    if msg_root.exists():
        for p in sorted(msg_root.glob("*.json")):
            messages.append(json.loads(p.read_text(encoding="utf-8")))

    by_trace = {}
    for s in spans:
        by_trace.setdefault(s["trace_id"], []).append(s)

    n_requests = len(by_trace) or len(messages)
    hits = sum(1 for m in messages if m.get("cache_hit"))
    misses = sum(1 for m in messages if not m.get("cache_hit"))
    if not messages:
        for sts in by_trace.values():
            cl = next((x for x in sts if x.get("stage") == "cache_lookup"), None)
            if not cl:
                continue
            if cl.get("cache_hit"):
                hits += 1
            else:
                misses += 1

    errors = [s for s in spans if s.get("status") == "error"]
    e2e = []
    for sts in by_trace.values():
        durs = [s["duration_ms"] for s in sts if "duration_ms" in s]
        if durs:
            e2e.append(sum(durs))

    starts = [s.get("start") for s in spans if s.get("start")]
    summary = {
        "n_requests": n_requests,
        "cache_hits": hits,
        "cache_misses": misses,
        "cache_hit_rate": (hits / (hits + misses)) if (hits + misses) else None,
        "n_error_spans": len(errors),
        "error_rate": (len(errors) / max(1, len(spans))) if spans else None,
        "e2e_latency_ms": {
            "p50": _percentile(e2e, 50),
            "p95": _percentile(e2e, 95),
            "mean": statistics.mean(e2e) if e2e else None,
            "n": len(e2e),
        },
        "time_window": {
            "start": min(starts) if starts else None,
            "end": max(s.get("end") for s in spans if s.get("end")) if spans else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "data_sources": {
            "spans": str(span_root or SPANS_DIR),
            "messages": str(msg_root),
        },
    }
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def build_trace_index(named=None):
    store = SpanStore()
    idx = {"all_trace_ids": store.list_trace_ids(), "named": named or {}}
    TRACE_INDEX_JSON.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")
    return idx
