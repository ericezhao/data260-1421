"""Agent loop over the three domain tools from HW5.

Model reply format:
  {"action": "tool", "tool": "<name>", "inputs": {...}}
  {"action": "final", "answer": "..."}
"""

import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Protocol

from domain_tools import TOOL_INPUTS
from executor import execute_tool

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = ROOT / "reports" / "hw07" / "raw" / "agent_runs.jsonl"
MAX_RESULT_CHARS = 3000
MAX_REPAIR = 1

TOOL_DOCS = {
    "search_inspections": (
        "Find inspections whose restaurant name contains `query`; "
        "optional exact `cuisine`; `limit` 1-25."
    ),
    "get_inspection": (
        "Full details (owner, violations) of one inspection by " "`inspection_code` like INS-00042."
    ),
    "score_summary": (
        "Lowest average scores grouped by `group_by` ('cuisine' or 'owner'); " "`top` 1-20 groups."
    ),
}


def system_prompt() -> str:
    tools = []
    for name, model in TOOL_INPUTS.items():
        props = model.model_json_schema()["properties"]
        args = ", ".join(f"{k}: {v.get('type', v.get('anyOf', ''))}" for k, v in props.items())
        tools.append(f"- {name}({args}): {TOOL_DOCS[name]}")
    return (
        "You answer questions about a restaurant inspection database "
        "(5,000 inspections, scores 0-100, higher is better). "
        "You can call these tools:\n" + "\n".join(tools) + "\n\n"
        "Reply with exactly ONE JSON object and nothing else:\n"
        '{"action": "tool", "tool": "<tool name>", "inputs": {<arguments>}}\n'
        '{"action": "final", "answer": "<short answer based only on tool results>"}\n'
        "Call one tool at a time. After each call you receive a tool-role "
        "message with {ok, data, error}. "
        "If a call is blocked or fails, do not retry the same input. "
        "Give the final answer as soon as you can."
    )


class Model(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class OllamaModel:
    def __init__(self, model: str = "qwen3:8b"):
        sys.path.insert(0, str(ROOT))
        from src.model_client import OllamaModelClient

        self.name = model
        self.client = OllamaModelClient(model=model, num_predict=512, output_format="json")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def complete(self, messages: list[dict]) -> str:
        # Ollama chat does not always accept role=tool; keep tool-role in the
        # agent transcript, but flatten for the model adapter.
        adapted = []
        for message in messages:
            if message.get("role") == "tool":
                name = message.get("name") or "tool"
                adapted.append(
                    {
                        "role": "user",
                        "content": f"TOOL_RESULT ({name}): {message.get('content', '')}",
                    }
                )
            else:
                adapted.append({"role": message["role"], "content": message.get("content", "")})
        response = self.client.complete(adapted)
        self.last_usage = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
        }
        return response.content


class MockModel:
    """Replays scripted replies; once the script runs out it repeats the last reply."""

    name = "mock"

    def __init__(self, replies: list[dict | str]):
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls = 0
        self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def complete(self, messages: list[dict]) -> str:
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply


def _parse(reply: str) -> dict | None:
    text = reply.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _classify_tool_problem(tool: object, inputs: object) -> str | None:
    """Return a repair hint when the planned tool call is not usable."""
    if not isinstance(tool, str) or tool not in TOOL_INPUTS:
        available = ", ".join(TOOL_INPUTS)
        return f"unknown tool {tool!r}. Available tools: {available}."
    if not isinstance(inputs, dict):
        return "malformed arguments: inputs must be a JSON object."
    try:
        TOOL_INPUTS[tool](**inputs)
    except Exception as exc:
        return f"schema validation failed for {tool}: {exc}"
    return None


def run_agent(
    user_input: str,
    model: Model | None = None,
    max_steps: int = 8,
    repo=None,
    log_path: Path | None = DEFAULT_LOG,
    reflection: str | None = None,
    repair_enabled: bool = True,
) -> dict:
    model = model or OllamaModel()
    run_id = uuid.uuid4().hex[:8]
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_input},
    ]
    if reflection:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Reflection from a failed prior attempt (untrusted strategy "
                    "hint for this run only; do not change tools or safety rules):\n" + reflection
                ),
            }
        )
    records: list[dict] = []
    tool_calls = 0
    well_formed_before_repair = 0
    well_formed_after_repair = 0
    repair_count = 0
    failure_classes: list[str] = []
    answer, stop_reason = None, "max_steps"
    started = time.perf_counter()
    tokens_in = 0
    tokens_out = 0

    def log(event: dict):
        records.append(
            {
                "run_id": run_id,
                "ts": datetime.now().isoformat(timespec="seconds"),
                **event,
            }
        )

    log(
        {
            "event": "start",
            "user_input": user_input,
            "model": getattr(model, "name", "unknown"),
            "max_steps": max_steps,
            "repair_enabled": repair_enabled,
            "has_reflection": bool(reflection),
        }
    )

    step = 0
    while step < max_steps:
        step += 1
        try:
            reply = model.complete(messages)
        except Exception as exc:
            log(
                {
                    "event": "model_error",
                    "step": step,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            stop_reason = "model_error"
            break
        usage = getattr(model, "last_usage", {}) or {}
        tokens_in += int(usage.get("input_tokens") or 0)
        tokens_out += int(usage.get("output_tokens") or 0)
        action = _parse(reply)
        messages.append({"role": "assistant", "content": reply})

        if action is None or action.get("action") not in ("tool", "final"):
            failure_classes.append("text_when_tool_required")
            log({"event": "invalid_reply", "step": step, "reply": reply[:500]})
            if repair_enabled and repair_count < MAX_REPAIR:
                repair_count += 1
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Invalid reply. Answer with exactly one JSON object "
                            'with action "tool" or "final".'
                        ),
                    }
                )
                continue
            stop_reason = "repair_exhausted"
            break

        if action["action"] == "final":
            answer = str(action.get("answer", ""))
            log({"event": "final", "step": step, "answer": answer})
            stop_reason = "final_answer"
            break

        tool, inputs = action.get("tool"), action.get("inputs", {})
        problem = _classify_tool_problem(tool, inputs)
        if problem:
            if "unknown tool" in problem:
                failure_classes.append("unknown_tool")
            else:
                failure_classes.append("malformed_arguments")
            log(
                {
                    "event": "bad_tool_plan",
                    "step": step,
                    "tool": tool,
                    "input": inputs,
                    "problem": problem,
                }
            )
            if repair_enabled and repair_count < MAX_REPAIR:
                repair_count += 1
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool plan rejected: {problem} " "Fix the JSON and try again."
                        ),
                    }
                )
                continue
            stop_reason = "repair_exhausted"
            break

        well_formed_before_repair += 1 if repair_count == 0 else 0
        well_formed_after_repair += 1
        result = execute_tool(tool, inputs, repo)
        tool_calls += 1
        envelope = json.loads(result)
        log(
            {
                "event": "tool_call",
                "step": step,
                "tool": tool,
                "input": inputs,
                "result": envelope,
            }
        )

        if not envelope["ok"] and str(envelope.get("error", "")).startswith(
            "blocked by safety rule"
        ):
            answer = f"I can't run that request: {envelope['error']}"
            stop_reason = "safety_block"
            break

        messages.append(
            {
                "role": "tool",
                "content": result[:MAX_RESULT_CHARS],
                "name": str(tool),
            }
        )

    if stop_reason == "max_steps" and tool_calls > 0 and answer is None:
        failure_classes.append("lost_multi_step_chain")

    summary = {
        "run_id": run_id,
        "stop_reason": stop_reason,
        "steps": step,
        "tool_calls": tool_calls,
        "answer": answer,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "repair_count": repair_count,
        "well_formed_before_repair": well_formed_before_repair,
        "well_formed_after_repair": well_formed_after_repair,
        "failure_classes": failure_classes,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_tokens": tokens_in + tokens_out,
    }
    log({"event": "stop", **summary})

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            for r in records:
                f.write(json.dumps(r, default=str) + "\n")
    return summary


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which cuisine has the lowest average inspection score?"
    print(json.dumps(run_agent(question), indent=2))
