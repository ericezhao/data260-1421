#!/usr/bin/env python3
# Part 4.2: one hit, one miss, one fail
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw10.config import RAW, TRACES_DIR
from hw10.evaluator import evaluate_artifact
from hw10.ops_summary import build_trace_index
from hw10.pipeline import handle_request
from hw10.tracing import SpanStore


def _copy_trace(tid, label):
    spans = SpanStore().load(tid)
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACES_DIR / f"{label}_{tid}.json"
    path.write_text(json.dumps(spans, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    named = {}
    mock_judge = os.getenv("HW10_MOCK_JUDGE") == "1"

    miss_id = f"miss-{uuid.uuid4().hex[:10]}"
    q = "What does a restaurant inspection score between 0 and 100 mean for diners?"
    print("[part4] miss", miss_id)
    handle_request(q, trace_id=miss_id, force_miss=True)
    try:
        evaluate_artifact(miss_id, mock=mock_judge)
    except Exception as e:
        print("[part4] eval warn:", e)
    _copy_trace(miss_id, "cache_miss")
    named["cache_miss_success"] = miss_id

    hit_id = f"hit-{uuid.uuid4().hex[:10]}"
    print("[part4] hit", hit_id)
    handle_request(q, trace_id=hit_id, force_miss=False)
    _copy_trace(hit_id, "cache_hit")
    named["cache_hit"] = hit_id

    fail_id = f"fail-{uuid.uuid4().hex[:10]}"
    print("[part4] fail", fail_id)
    try:
        handle_request(
            "failure probe",
            trace_id=fail_id,
            force_miss=True,
            fail_stage="writer",
            skip_cache_store=True,
        )
    except Exception as e:
        print("[part4] expected fail:", e)
    _copy_trace(fail_id, "failed")
    named["failed"] = fail_id
    spans = SpanStore().load(fail_id)
    err = next((s for s in spans if s.get("status") == "error"), None)
    named["failed_stage"] = (err or {}).get("stage")
    named["failed_error"] = (err or {}).get("error")

    build_trace_index(named)
    (RAW / "part4_named_traces.json").write_text(json.dumps(named, indent=2) + "\n")
    print(json.dumps(named, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
