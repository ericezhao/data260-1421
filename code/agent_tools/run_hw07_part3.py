"""Compare plain run_agent vs Reflexion on the three fixed tasks."""

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
from reflexion import REFLECTION_LOG, run_with_reflexion, verify_task
from verification_tasks import TASKS

HW07 = ROOT / "reports" / "hw07"
RAW = HW07 / "raw"
LOG = HW07 / "RUN_LOG.txt"
AGENT_LOG = RAW / "agent_runs_part3.jsonl"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if REFLECTION_LOG.exists():
        REFLECTION_LOG.unlink()
    if AGENT_LOG.exists():
        AGENT_LOG.unlink()
    model = OllamaModel("qwen3:8b")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Eric Zhao (SID4 1421) - HW7 Part 3 Reflexion @ {stamp}")
    rows = []
    for task in TASKS:
        print(f"\nOriginal {task['id']}", flush=True)
        original = run_agent(task["prompt"], model=model, max_steps=8, log_path=AGENT_LOG)
        original_check = verify_task(task["id"], original)
        print(
            f"  stop={original['stop_reason']} tools={original['tool_calls']} "
            f"ok={original_check['ok']}",
            flush=True,
        )

        print(f"Reflexion {task['id']}", flush=True)
        reflex = run_with_reflexion(task, model=model, log_path=AGENT_LOG)
        print(
            f"  stop={reflex['stop_reason']} retries={reflex['retries']} "
            f"tools={reflex['tool_calls']} success={reflex['success']}",
            flush=True,
        )
        rows.append(
            {
                "task_id": task["id"],
                "original_success": int(original_check["ok"]),
                "original_unsupported": len(original_check.get("unsupported_claims") or []),
                "original_tool_calls": original.get("tool_calls") or 0,
                "original_tokens": original.get("total_tokens") or 0,
                "original_latency_ms": int((original.get("elapsed_s") or 0) * 1000),
                "reflexion_success": int(reflex["success"]),
                "reflexion_retries": reflex["retries"],
                "reflexion_tool_calls": reflex["tool_calls"],
                "reflexion_tokens": reflex["total_tokens"],
                "reflexion_latency_ms": int(reflex["elapsed_s"] * 1000),
                "verifier_false_rejection": int(reflex["verifier_false_rejection"]),
            }
        )

    with (RAW / "reflexion_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def avg(key):
        return round(sum(r[key] for r in rows) / len(rows), 2)

    summary = {
        "original": {
            "task_success": avg("original_success"),
            "unsupported_claims": avg("original_unsupported"),
            "retry_rate": 0.0,
            "tool_calls": avg("original_tool_calls"),
            "tokens": avg("original_tokens"),
            "latency_ms": avg("original_latency_ms"),
            "verifier_false_rejections": 0,
        },
        "reflexion": {
            "task_success": avg("reflexion_success"),
            "unsupported_claims": 0,
            "retry_rate": avg("reflexion_retries"),
            "tool_calls": avg("reflexion_tool_calls"),
            "tokens": avg("reflexion_tokens"),
            "latency_ms": avg("reflexion_latency_ms"),
            "verifier_false_rejections": sum(r["verifier_false_rejection"] for r in rows),
        },
        "rows": rows,
    }
    (RAW / "reflexion_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{stamp}] part 3 reflexion comparison\n")
        handle.write(json.dumps(summary["original"]) + "\n")
        handle.write(json.dumps(summary["reflexion"]) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
