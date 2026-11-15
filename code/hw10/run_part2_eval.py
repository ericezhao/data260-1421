#!/usr/bin/env python3
# Part 2: one e2e question -> join by correlation_id -> score
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw10.config import RAW
from hw10.evaluator import evaluate_artifact
from hw10.pipeline import handle_request


def main():
    q = os.getenv(
        "HW10_TEST_QUESTION",
        "Why do sushi restaurants care about health inspection scores (0-100)?",
    )
    tid = os.getenv("HW10_TRACE_ID", f"part2-{uuid.uuid4().hex[:12]}")
    print(f"[part2] tid={tid} mock={os.getenv('HW10_MOCK_LLM')}")
    rec = handle_request(q, trace_id=tid, force_miss=True)
    print("[part2] cache_hit=", rec.get("cache_hit"))
    ev = evaluate_artifact(tid, mock=(os.getenv("HW10_MOCK_JUDGE") == "1"))
    # if draft == final, keep that in interpretation
    fvd = (ev.get("metrics") or {}).get("final_vs_draft") or {}
    if fvd.get("diff") == 0 or fvd.get("engine") == "same_text":
        ev["note"] = "final same as draft — reviewer did not improve it"
    out = RAW / "part2_eval.json"
    out.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    scores = {k: v.get("score") for k, v in (ev.get("metrics") or {}).items()}
    print(json.dumps({"trace_id": tid, "scores": scores, "path": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
