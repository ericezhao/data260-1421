"""Run the three verification tasks, error recovery, and 20 reliability attempts."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS), str(ROOT)]

from agent import OllamaModel, run_agent
from verification_tasks import ERROR_RECOVERY, TASKS

HW07 = ROOT / "reports" / "hw07"
RAW = HW07 / "raw"
LOG = HW07 / "RUN_LOG.txt"
AGENT_LOG = RAW / "agent_runs.jsonl"


def append_log(text: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(text)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if AGENT_LOG.exists():
        AGENT_LOG.unlink()
    model = OllamaModel("qwen3:8b")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Eric Zhao (SID4 1421) - HW7 Part 2 @ {stamp}")
    append_log(f"\n[{stamp}] part 2 verification + reliability\n")

    task_rows = []
    for task in TASKS:
        print(f"\nTask {task['id']}: {task['title']}", flush=True)
        result = run_agent(task["prompt"], model=model, max_steps=8, log_path=AGENT_LOG)
        print(
            f"  stop={result['stop_reason']} tools={result['tool_calls']} "
            f"answer={str(result['answer'])[:160]!r}",
            flush=True,
        )
        append_log(
            f"task {task['id']}: stop={result['stop_reason']} "
            f"tools={result['tool_calls']} answer={result['answer']}\n"
        )
        task_rows.append({"task_id": task["id"], **result})

    print("\nError recovery", flush=True)
    err = run_agent(ERROR_RECOVERY["prompt"], model=model, max_steps=5, log_path=AGENT_LOG)
    print(
        f"  stop={err['stop_reason']} tools={err['tool_calls']} "
        f"answer={str(err['answer'])[:200]!r}",
        flush=True,
    )
    append_log(
        f"error recovery: stop={err['stop_reason']} tools={err['tool_calls']} "
        f"answer={err['answer']}\n"
    )

    attempts = []
    for i in range(20):
        task = TASKS[i % len(TASKS)]
        # Half the attempts disable repair to measure before/after rates.
        repair = i % 2 == 1
        result = run_agent(
            task["prompt"],
            model=model,
            max_steps=8,
            log_path=AGENT_LOG,
            repair_enabled=repair,
        )
        attempts.append(
            {
                "attempt": i + 1,
                "task_id": task["id"],
                "repair_enabled": repair,
                "stop_reason": result["stop_reason"],
                "tool_calls": result["tool_calls"],
                "well_formed_before_repair": result["well_formed_before_repair"],
                "well_formed_after_repair": result["well_formed_after_repair"],
                "repair_count": result["repair_count"],
                "failure_classes": "|".join(result.get("failure_classes") or []),
                "answer": (result.get("answer") or "").replace("\n", " ")[:240],
            }
        )
        print(
            f"reliability {i+1}/20 task={task['id']} repair={repair} "
            f"stop={result['stop_reason']} tools={result['tool_calls']}",
            flush=True,
        )

    with (RAW / "reliability_attempts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(attempts[0].keys()))
        writer.writeheader()
        writer.writerows(attempts)

    before = [a for a in attempts if not a["repair_enabled"]]
    after = [a for a in attempts if a["repair_enabled"]]

    def rate(rows, key):
        total_calls = sum(max(1, r["tool_calls"] + r["repair_count"]) for r in rows) or 1
        good = sum(r[key] for r in rows)
        return round(100.0 * good / total_calls, 1)

    summary = {
        "well_formed_rate_before_repair_pct": rate(before, "well_formed_before_repair"),
        "well_formed_rate_after_repair_pct": rate(after, "well_formed_after_repair"),
        "failure_class_counts": {},
    }
    for row in attempts:
        for item in row["failure_classes"].split("|") if row["failure_classes"] else []:
            summary["failure_class_counts"][item] = summary["failure_class_counts"].get(item, 0) + 1
    (RAW / "reliability_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    append_log(json.dumps(summary) + "\n")
    (RAW / "part2_task_results.json").write_text(
        json.dumps({"tasks": task_rows, "error_recovery": err}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
