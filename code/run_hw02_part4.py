import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
_ROOT = _CODE_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from src.model_client import OllamaModelClient
from restaurant_graph.workflow import classify_schema_run, make_state, run_graph

CASES = _ROOT / "reports" / "hw02" / "cases"
RAW = _ROOT / "reports" / "hw02" / "raw"


def load_case(name: str) -> dict:
    return json.loads((CASES / name).read_text(encoding="utf-8"))


def make_llm():
    return OllamaModelClient(output_format="json", temperature=0.0)


def run_batch(case: dict, n: int, max_turns: int, label: str) -> list[dict]:
    llm = make_llm()
    rows = []
    RAW.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        print(f"\n=== {label} run {i}/{n} max_turns={max_turns} ===")
        state = make_state(
            llm,
            case["title"],
            case["content"],
            case.get("email", "eric.e.zhao@sjsu.edu"),
            max_turns=max_turns,
            schema_only=True,
        )
        final, latency_ms = run_graph(state)
        outcome = classify_schema_run(final)
        row = {
            "run": i,
            "outcome": outcome,
            "planner_attempts": int(final.get("planner_attempts") or 0),
            "validation_error": final.get("validation_error") or "",
            "latency_ms": latency_ms,
            "tags": ((final.get("planner_proposal") or {}).get("data") or {}).get("tags"),
            "summary": ((final.get("planner_proposal") or {}).get("data") or {}).get("summary"),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    return rows


def summarize(rows: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in rows)
    latencies = [row["latency_ms"] for row in rows]
    completed = [row for row in rows if row["outcome"] != "hit_ceiling"]
    return {
        "n": len(rows),
        "counts": dict(counts),
        "completion_rate": round(len(completed) / len(rows), 3) if rows else 0,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "mean_latency_completed_ms": (
            round(sum(r["latency_ms"] for r in completed) / len(completed), 1)
            if completed
            else None
        ),
    }


def save(name: str, payload: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path}")


def mean_latency(rows: list[dict], outcome: str) -> str:
    subset = [row for row in rows if row.get("outcome") == outcome]
    if not subset:
        return "—"
    return f"{round(sum(row['latency_ms'] for row in subset) / len(subset), 1)}"


def load_raw(name: str) -> dict | None:
    path = RAW / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_metrics() -> None:
    schema = load_raw("schema_runs.json")
    ceiling = load_raw("ceiling_runs.json")
    adversarial = load_raw("adversarial_runs.json")

    lines = [
        "# HW2 Part 4 metrics",
        "",
        "Frozen schema input: `reports/hw02/cases/schema_input.json`",
        "Model: `qwen3:8b` via `src/model_client.py`",
        "",
        "## Outcome over 30 runs",
        "",
        "| Outcome over 30 runs | Count | Mean latency (ms) |",
        "| --- | --- | --- |",
    ]

    if schema and schema.get("runs"):
        rows = schema["runs"]
        counts = Counter(row["outcome"] for row in rows)
        lines.extend(
            [
                f"| Valid first attempt | {counts.get('valid_first_attempt', 0)} | {mean_latency(rows, 'valid_first_attempt')} |",
                f"| Valid after 1 retry | {counts.get('valid_after_1_retry', 0)} | {mean_latency(rows, 'valid_after_1_retry')} |",
                f"| Valid after 2+ retries | {counts.get('valid_after_2plus_retries', 0)} | {mean_latency(rows, 'valid_after_2plus_retries')} |",
                f"| Hit turn ceiling | {counts.get('hit_ceiling', 0)} | {mean_latency(rows, 'hit_ceiling')} |",
            ]
        )
    else:
        lines.extend(
            [
                "| Valid first attempt |  |  |",
                "| Valid after 1 retry |  |  |",
                "| Valid after 2+ retries |  |  |",
                "| Hit turn ceiling |  |  |",
            ]
        )

    lines.extend(
        [
            "",
            "Source: `reports/hw02/raw/schema_runs.json`",
            "",
            "## Turn ceiling 2 vs 10 (20 runs each)",
            "",
            "| Ceiling | Completion rate | Mean latency (ms) |",
            "| --- | --- | --- |",
        ]
    )

    choice = "*(fill after the ceiling runs)*"
    if ceiling and "ceiling_2" in ceiling and "ceiling_10" in ceiling:
        c2 = ceiling["ceiling_2"]
        c10 = ceiling["ceiling_10"]
        lines.extend(
            [
                f"| 2 | {c2['completion_rate']:.3f} | {c2['mean_latency_ms']} |",
                f"| 10 | {c10['completion_rate']:.3f} | {c10['mean_latency_ms']} |",
            ]
        )
        if c2["completion_rate"] > c10["completion_rate"]:
            choice = "**2**. Higher completion rate than ceiling 10 on this frozen input."
        elif c10["completion_rate"] > c2["completion_rate"]:
            choice = "**10**. Higher completion rate; the extra retries recovered runs that ceiling 2 abandoned."
        elif c2["mean_latency_ms"] <= c10["mean_latency_ms"]:
            choice = (
                "**2**. Both ceilings completed at the same rate. Ceiling 2 is as fast or faster "
                "and stops sooner on invalid output."
            )
        else:
            choice = "**10**. Completion rate matched ceiling 2; keep 10 if you want more retry budget."
    else:
        lines.extend(["| 2 |  |  |", "| 10 |  |  |"])

    lines.extend(
        [
            "",
            f"Chosen for deployment: {choice}",
            "",
            "Source: `reports/hw02/raw/ceiling_runs.json`",
            "",
            "## Adversarial input (5 runs)",
            "",
            "Input: `reports/hw02/cases/adversarial_input.json`",
            "",
            "| Hit ceiling | Other outcomes | Notes |",
            "| --- | --- | --- |",
        ]
    )

    if adversarial and adversarial.get("runs"):
        rows = adversarial["runs"]
        counts = Counter(row["outcome"] for row in rows)
        hit = counts.get("hit_ceiling", 0)
        other = len(rows) - hit
        lines.append(
            f"| {hit} | {other} | {json.dumps(dict(counts), ensure_ascii=False)} |"
        )
    else:
        lines.append("|  |  | Not run yet. |")

    lines.extend(
        [
            "",
            "Why it causes trouble: the input tells the model to emit one-letter tags `a,b,c` as a comma string and a 40-word summary, so Pydantic rejects `data.tags` (not a list of 3 tags each 3–30 characters) and the graph retries until the ceiling.",
            "",
            "Proposed fix: reject non-list tags before another LLM call, or clamp/repair tags and summary with a deterministic post-processor after the first failure.",
            "",
            "Source: `reports/hw02/raw/adversarial_runs.json`",
            "",
        ]
    )

    path = _ROOT / "reports" / "hw02" / "METRICS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--experiment",
        choices=["schema", "ceiling", "adversarial", "all"],
        default="all",
    )
    args = ap.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    schema_case = load_case("schema_input.json")
    adversarial_case = load_case("adversarial_input.json")

    if args.experiment in ("schema", "all"):
        rows = run_batch(schema_case, 30, max_turns=10, label="schema30")
        save(
            "schema_runs.json",
            {"started": started, "input": schema_case, "max_turns": 10, "summary": summarize(rows), "runs": rows},
        )

    if args.experiment in ("ceiling", "all"):
        rows2 = run_batch(schema_case, 20, max_turns=2, label="ceiling2")
        rows10 = run_batch(schema_case, 20, max_turns=10, label="ceiling10")
        save(
            "ceiling_runs.json",
            {
                "started": started,
                "input": schema_case,
                "ceiling_2": summarize(rows2),
                "ceiling_10": summarize(rows10),
                "runs_2": rows2,
                "runs_10": rows10,
            },
        )

    if args.experiment in ("adversarial", "all"):
        rows = run_batch(adversarial_case, 5, max_turns=10, label="adversarial")
        save(
            "adversarial_runs.json",
            {"started": started, "input": adversarial_case, "max_turns": 10, "summary": summarize(rows), "runs": rows},
        )

    print("done", datetime.now(timezone.utc).isoformat())
    write_metrics()


if __name__ == "__main__":
    main()
