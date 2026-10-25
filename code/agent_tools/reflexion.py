"""Retry a failed verification task with one short reflection in context."""

import json
import re
import time
from pathlib import Path

from agent import DEFAULT_LOG, run_agent
from verification_tasks import TASKS

ROOT = Path(__file__).resolve().parents[2]
REFLECTION_LOG = ROOT / "reports" / "hw07" / "raw" / "reflections.jsonl"
MAX_REFLEXION_RETRIES = 2
TOOL_BUDGET = 10
TOKEN_BUDGET = 12000


def _has_code(answer: str) -> bool:
    return bool(re.search(r"INS-\d{5}", answer or "", re.I))


def _has_number(answer: str) -> bool:
    return bool(re.search(r"\b\d{2,3}\b", answer or ""))


def verify_task(task_id: str, result: dict) -> dict:
    """Return {ok, assertion, evidence} for a finished agent run."""
    answer = (result.get("answer") or "").strip()
    tools = result.get("tool_calls") or 0
    stop = result.get("stop_reason")
    evidence = {
        "stop_reason": stop,
        "tool_calls": tools,
        "answer_excerpt": answer[:240],
    }

    if stop != "final_answer" or not answer:
        return {
            "ok": False,
            "assertion": "expected a final_answer with non-empty text",
            "evidence": evidence,
        }

    task = next(item for item in TASKS if item["id"] == task_id)
    if tools < task["min_tool_calls"]:
        return {
            "ok": False,
            "assertion": (f"expected at least {task['min_tool_calls']} tool calls, got {tools}"),
            "evidence": evidence,
        }

    if task_id == "A":
        if not (_has_code(answer) and _has_number(answer)):
            return {
                "ok": False,
                "assertion": "answer must include an INS-##### code and a score",
                "evidence": evidence,
            }
    elif task_id == "B":
        if "cuisine" not in answer.lower() and not re.search(
            r"japanese|american|chinese|mexican|italian|thai|indian",
            answer,
            re.I,
        ):
            return {
                "ok": False,
                "assertion": "answer must name a cuisine",
                "evidence": evidence,
            }
        if not _has_code(answer):
            return {
                "ok": False,
                "assertion": "answer must include a supporting INS-##### example",
                "evidence": evidence,
            }
    elif task_id == "C":
        if not (_has_code(answer) and _has_number(answer)):
            return {
                "ok": False,
                "assertion": "comparison must mention a code and a score",
                "evidence": evidence,
            }
        if tools < 3:
            return {
                "ok": False,
                "assertion": "comparison needs search plus two detail lookups",
                "evidence": evidence,
            }

    unsupported = []
    if "phone" in answer.lower() or "@" in answer:
        unsupported.append("answer appears to include contact data")
    return {
        "ok": True,
        "assertion": "passed deterministic checks",
        "evidence": evidence,
        "unsupported_claims": unsupported,
    }


def write_reflection(task_id: str, result: dict, check: dict) -> str:
    """Short failure explanation + revised strategy. No hidden chain-of-thought."""
    assertion = check.get("assertion", "failed")
    tools = result.get("tool_calls", 0)
    stop = result.get("stop_reason")
    text = (
        f"Task {task_id} failed: {assertion}. "
        f"Prior stop={stop}, tool_calls={tools}. "
        "Revised strategy: call the required tools in order, use only values "
        "returned by tools, and finish with a final answer that includes the "
        "inspection codes and scores needed by the check."
    )
    return text


def run_with_reflexion(
    task: dict,
    model=None,
    repo=None,
    log_path: Path | None = DEFAULT_LOG,
    reflection_path: Path | None = REFLECTION_LOG,
) -> dict:
    started = time.perf_counter()
    reflection = None
    attempts = []
    total_tools = 0
    total_tokens = 0
    stop_reason = "human_review"
    final = None
    false_reject = False

    for attempt in range(MAX_REFLEXION_RETRIES + 1):
        if total_tools >= TOOL_BUDGET or total_tokens >= TOKEN_BUDGET:
            stop_reason = "budget_exhausted"
            break
        result = run_agent(
            task["prompt"],
            model=model,
            max_steps=8,
            repo=repo,
            log_path=log_path,
            reflection=reflection,
            repair_enabled=True,
        )
        total_tools += int(result.get("tool_calls") or 0)
        total_tokens += int(result.get("total_tokens") or 0)
        check = verify_task(task["id"], result)
        attempts.append(
            {
                "attempt": attempt + 1,
                "result": {
                    "run_id": result.get("run_id"),
                    "stop_reason": result.get("stop_reason"),
                    "tool_calls": result.get("tool_calls"),
                    "answer": result.get("answer"),
                    "total_tokens": result.get("total_tokens"),
                    "elapsed_s": result.get("elapsed_s"),
                },
                "check": check,
                "reflection_used": reflection,
            }
        )
        if check["ok"]:
            stop_reason = "success"
            final = result
            break
        if attempt >= MAX_REFLEXION_RETRIES:
            stop_reason = "human_review"
            final = result
            break
        reflection = write_reflection(task["id"], result, check)
        if reflection_path is not None:
            reflection_path.parent.mkdir(parents=True, exist_ok=True)
            with open(reflection_path, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "task_id": task["id"],
                            "run_id": result.get("run_id"),
                            "assertion": check.get("assertion"),
                            "evidence": check.get("evidence"),
                            "reflection": reflection,
                        },
                        default=str,
                    )
                    + "\n"
                )

    # Heuristic note: if the last attempt had a final answer with codes/scores
    # but the verifier still failed, mark a possible false rejection for metrics.
    if (
        stop_reason != "success"
        and final
        and final.get("stop_reason") == "final_answer"
        and _has_code(final.get("answer") or "")
        and _has_number(final.get("answer") or "")
    ):
        false_reject = True

    return {
        "task_id": task["id"],
        "stop_reason": stop_reason,
        "attempts": attempts,
        "retries": max(0, len(attempts) - 1),
        "tool_calls": total_tools,
        "total_tokens": total_tokens,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "answer": (final or {}).get("answer"),
        "verifier_false_rejection": false_reject,
        "success": stop_reason == "success",
    }
