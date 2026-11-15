# spearman / mae / repeatability
import csv
import json
import statistics
from pathlib import Path

from hw10.config import HUMAN_LABELS_CSV, REPORTS_DIR


def load_human_labels(path=None):
    path = Path(path) if path else HUMAN_LABELS_CSV
    rows = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "case_id": row["case_id"],
                    "human_score": float(row["human_score"]),
                    "notes": row.get("notes") or "",
                }
            )
    return rows


def spearman_rho(xs, ys):
    try:
        from scipy.stats import spearmanr

        rho, p = spearmanr(xs, ys)
        return float(rho), float(p)
    except Exception:
        # simple rank corr fallback
        def ranks(vals):
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            r = [0.0] * len(vals)
            i = 0
            while i < len(vals):
                j = i
                while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                    j += 1
                avg = (i + j) / 2.0 + 1.0
                for k in range(i, j + 1):
                    r[order[k]] = avg
                i = j + 1
            return r

        rx, ry = ranks(list(xs)), ranks(list(ys))
        n = len(rx)
        mx, my = sum(rx) / n, sum(ry) / n
        num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        denx = sum((a - mx) ** 2 for a in rx) ** 0.5
        deny = sum((b - my) ** 2 for b in ry) ** 0.5
        rho = num / (denx * deny) if denx and deny else 0.0
        return float(rho), float("nan")


def mae(xs, ys):
    return sum(abs(a - b) for a, b in zip(xs, ys)) / max(1, len(xs))


def agreement_report(judge_scores_by_case, human_rows=None):
    human_rows = human_rows or load_human_labels()
    xs, ys, paired = [], [], []
    for h in human_rows:
        cid = h["case_id"]
        if cid not in judge_scores_by_case:
            continue
        j = float(judge_scores_by_case[cid])
        xs.append(h["human_score"])
        ys.append(j)
        paired.append({"case_id": cid, "human": h["human_score"], "judge": j})
    rho, p = spearman_rho(xs, ys) if len(xs) >= 2 else (0.0, float("nan"))
    return {
        "n": len(xs),
        "spearman_rho": rho,
        "spearman_p": p,
        "mae": mae(xs, ys) if xs else None,
        "pairs": paired,
    }


def repeatability(scores_runs):
    if not scores_runs:
        return {"n_runs": 0, "per_case": {}, "mean_stdev": None}
    keys = set()
    for run in scores_runs:
        keys |= set(run)
    per = {}
    stdevs = []
    for k in sorted(keys):
        vals = [run[k] for run in scores_runs if k in run]
        if len(vals) < 2:
            continue
        sd = statistics.pstdev(vals)
        per[k] = {"scores": vals, "stdev": sd, "mean": statistics.mean(vals)}
        stdevs.append(sd)
    return {
        "n_runs": len(scores_runs),
        "per_case": per,
        "mean_stdev": statistics.mean(stdevs) if stdevs else None,
        "max_stdev": max(stdevs) if stdevs else None,
    }


def write_judge_metrics(payload, name="judge_metrics.json"):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
