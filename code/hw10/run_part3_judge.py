#!/usr/bin/env python3
# Part 3: judge 20 frozen drafts x3, spearman / mae / repeat
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw10.config import EVAL_CASES_JSON, JUDGE_METRICS_JSON, JUDGE_MODEL, JUDGE_REPEAT_N, RAW
from hw10.judge import CRITERIA, score_with_criteria
from hw10.metrics_judge import (
    agreement_report,
    load_human_labels,
    repeatability,
    write_judge_metrics,
)


def score_cases(cases, mock=None):
    out = {}
    details = {}
    for c in cases:
        scored = score_with_criteria(
            "writer_helpfulness",
            CRITERIA["writer_helpfulness"],
            c["question"],
            c["draft"],
            mock=mock,
        )
        out[c["case_id"]] = scored["score"]
        details[c["case_id"]] = scored
    return out, details


def main():
    mock = os.getenv("HW10_MOCK_JUDGE") == "1"
    cases = json.loads(EVAL_CASES_JSON.read_text(encoding="utf-8"))
    assert len(cases) == 20
    humans = load_human_labels()
    assert len(humans) == 20

    runs = []
    for i in range(JUDGE_REPEAT_N):
        print(f"[part3] run {i+1}/{JUDGE_REPEAT_N} mock={mock}")
        scores, details = score_cases(cases, mock=mock)
        runs.append(scores)
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / f"judge_run_{i+1}.json").write_text(
            json.dumps(details, indent=2) + "\n", encoding="utf-8"
        )

    agree = agreement_report(runs[0], humans)
    rep = repeatability(runs)

    change_abs = []
    change_count = 0
    for k in sorted(runs[0]):
        vals = [run[k] for run in runs]
        if len(set(vals)) > 1:
            change_count += 1
        change_abs.append(max(vals) - min(vals))

    payload = {
        "judge_model": JUDGE_MODEL,
        "mock": mock,
        "n_cases": 20,
        "n_runs": JUDGE_REPEAT_N,
        "agreement_run1": agree,
        "repeatability": {
            "cases_with_any_change": change_count,
            "fraction_changed": change_count / 20.0,
            "mean_abs_change": sum(change_abs) / 20.0,
            "max_abs_change": max(change_abs) if change_abs else 0,
            "mean_stdev": rep["mean_stdev"],
            "max_stdev": rep["max_stdev"],
            "per_case": rep["per_case"],
        },
        "trust_gate": {
            "would_trust_to_gate_deploy": False,
            "reason": (
                "spearman only ~0.4 and judge is a bit optimistic; "
                "need holdout + thresholds first"
            ),
        },
        "run1_scores": runs[0],
    }
    write_judge_metrics(payload, name="raw/judge_metrics.json")
    JUDGE_METRICS_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "spearman": agree["spearman_rho"],
                "mae": agree["mae"],
                "changed": change_count,
                "mean_abs_change": payload["repeatability"]["mean_abs_change"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
