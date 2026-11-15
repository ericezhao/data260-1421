#!/usr/bin/env python3
# quick checks for hw10 deliverables
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw10.config import (
    EVAL_CASES_JSON,
    HUMAN_LABELS_CSV,
    JUDGE_METRICS_JSON,
    LATENCY_JSON,
    REPORTS,
    SPANS_DIR,
    TRACE_INDEX_JSON,
)


def check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": detail}


def main():
    checks = []

    cases = json.loads(EVAL_CASES_JSON.read_text())
    checks.append(check("eval_cases_20", len(cases) == 20, len(cases)))
    with HUMAN_LABELS_CSV.open() as f:
        labels = list(csv.DictReader(f))
    checks.append(check("human_labels_20", len(labels) == 20, len(labels)))
    scores = {r["case_id"]: int(r["human_score"]) for r in labels}
    checks.append(check("human_scores_1_5", all(1 <= scores[c["case_id"]] <= 5 for c in cases)))

    part2 = REPORTS / "raw" / "part2_eval.json"
    checks.append(check("part2_eval_exists", part2.exists()))
    if part2.exists():
        ev = json.loads(part2.read_text())
        m = ev.get("metrics") or {}
        need = {"plan_quality", "writer_helpfulness", "final_helpfulness", "final_vs_draft"}
        checks.append(check("part2_criteria", need <= set(m), sorted(m)))
        checks.append(check("part2_scale_1_5", all(1 <= m[k]["score"] <= 5 for k in m)))

    checks.append(check("judge_metrics", JUDGE_METRICS_JSON.exists()))
    if JUDGE_METRICS_JSON.exists():
        jm = json.loads(JUDGE_METRICS_JSON.read_text())
        agr = jm.get("agreement_run1") or {}
        checks.append(check("spearman_present", "spearman_rho" in agr, agr.get("spearman_rho")))
        checks.append(check("mae_present", agr.get("mae") is not None, agr.get("mae")))
        checks.append(check("pairs_20", len(agr.get("pairs") or []) == 20))
        checks.append(check("repeat_3", jm.get("n_runs") == 3, jm.get("n_runs")))
        checks.append(check("repeat_stats", "mean_abs_change" in (jm.get("repeatability") or {})))

    checks.append(check("trace_index", TRACE_INDEX_JSON.exists()))
    if TRACE_INDEX_JSON.exists():
        named = json.loads(TRACE_INDEX_JSON.read_text()).get("named") or {}
        for key in ("cache_hit", "cache_miss_success", "failed"):
            tid = named.get(key)
            ok = bool(tid) and (SPANS_DIR / f"{tid}.jsonl").exists()
            checks.append(check(f"trace_{key}", ok, tid))
        fail_tid = named.get("failed")
        if fail_tid:
            spans = [
                json.loads(line)
                for line in (SPANS_DIR / f"{fail_tid}.jsonl").read_text().splitlines()
                if line.strip()
            ]
            err = [s for s in spans if s.get("status") == "error"]
            checks.append(check("failed_has_error_span", bool(err), err[0] if err else None))

    checks.append(check("latency_json", LATENCY_JSON.exists()))
    if LATENCY_JSON.exists():
        lat = json.loads(LATENCY_JSON.read_text())
        checks.append(
            check(
                "latency_50_miss",
                lat.get("n_verified_cache_miss", 0) >= 50,
                lat.get("n_verified_cache_miss"),
            )
        )
        stages = {r["stage"] for r in lat.get("stages") or []}
        need_s = {"cache_lookup", "planner", "writer", "reviewer", "queue_wait", "eval"}
        checks.append(check("latency_stages", need_s <= stages, sorted(stages)))

    checks.append(check("streamlit_app", (ROOT / "code" / "hw10" / "app.py").exists()))
    checks.append(check("metrics_md", (REPORTS / "METRICS.md").exists()))
    checks.append(check("ai_use", (REPORTS / "AI_USE.md").exists()))
    checks.append(check("run_log", (REPORTS / "RUN_LOG.txt").exists()))

    passed = sum(1 for c in checks if c["ok"])
    out = {"passed": passed, "total": len(checks), "details": checks}
    (REPORTS / "verification.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
