"""Part 5: agent loop over the three domain tools with a local Ollama model.

The model answers every turn with one JSON object:
  {"action": "tool", "tool": "<name>", "inputs": {...}}   or   {"action": "final", "answer": "..."}
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
DEFAULT_LOG = ROOT / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
MAX_RESULT_CHARS = 3000

TOOL_DOCS = {
    "search_inspections": "Find inspections whose restaurant name contains `query`; optional exact `cuisine`; `limit` 1-25.",
    "get_inspection": "Full details (owner, violations) of one inspection by `inspection_code` like INS-00042.",
    "score_summary": "Lowest average scores grouped by `group_by` ('cuisine' or 'owner'); `top` 1-20 groups.",
}


def system_prompt() -> str:
    tools = []
    for name, model in TOOL_INPUTS.items():
        props = model.model_json_schema()["properties"]
        args = ", ".join(f"{k}: {v.get('type', v.get('anyOf', ''))}" for k, v in props.items())
        tools.append(f"- {name}({args}): {TOOL_DOCS[name]}")
    return (
        "You answer questions about a restaurant inspection database (5,000 inspections, scores 0-100, "
        "higher is better). You can call these tools:\n" + "\n".join(tools) + "\n\n"
        "Reply with exactly ONE JSON object and nothing else:\n"
        '{"action": "tool", "tool": "<tool name>", "inputs": {<arguments>}}\n'
        '{"action": "final", "answer": "<short answer based only on tool results>"}\n'
        "Call one tool at a time. After each call you receive TOOL_RESULT with {ok, data, error}. "
        "If a call is blocked or fails, do not retry the same input. Give the final answer as soon as you can."
    )


class Model(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class OllamaModel:
    def __init__(self, model: str = "qwen3:8b"):
        sys.path.insert(0, str(ROOT))
        from src.model_client import OllamaModelClient

        self.name = model
        self.client = OllamaModelClient(model=model, num_predict=512, output_format="json")

    def complete(self, messages: list[dict]) -> str:
        return self.client.complete(messages).content


class MockModel:
    """Replays scripted replies; once the script runs out it repeats the last reply."""

    name = "mock"

    def __init__(self, replies: list[dict | str]):
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls = 0

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


def run_agent(
    user_input: str,
    model: Model | None = None,
    max_steps: int = 5,
    repo=None,
    log_path: Path | None = DEFAULT_LOG,
) -> dict:
    model = model or OllamaModel()
    run_id = uuid.uuid4().hex[:8]
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_input}]
    records: list[dict] = []
    tool_calls = 0
    answer, stop_reason = None, "max_steps"
    started = time.perf_counter()

    def log(event: dict):
        records.append({"run_id": run_id, "ts": datetime.now().isoformat(timespec="seconds"), **event})

    log({"event": "start", "user_input": user_input, "model": getattr(model, "name", "unknown"), "max_steps": max_steps})

    step = 0
    while step < max_steps:
        step += 1
        try:
            reply = model.complete(messages)
        except Exception as exc:
            log({"event": "model_error", "step": step, "error": f"{type(exc).__name__}: {exc}"})
            stop_reason = "model_error"
            break
        action = _parse(reply)
        messages.append({"role": "assistant", "content": reply})

        if action is None or action.get("action") not in ("tool", "final"):
            log({"event": "invalid_reply", "step": step, "reply": reply[:500]})
            messages.append({"role": "user", "content": "Invalid reply. Answer with exactly one JSON object as instructed."})
            continue

        if action["action"] == "final":
            answer = str(action.get("answer", ""))
            log({"event": "final", "step": step, "answer": answer})
            stop_reason = "final_answer"
            break

        tool, inputs = action.get("tool"), action.get("inputs", {})
        result = execute_tool(tool, inputs, repo)
        tool_calls += 1
        envelope = json.loads(result)
        log({"event": "tool_call", "step": step, "tool": tool, "input": inputs, "result": envelope})

        if not envelope["ok"] and envelope["error"].startswith("blocked by safety rule"):
            answer = f"I can't run that request: {envelope['error']}"
            stop_reason = "safety_block"
            break
        messages.append({"role": "user", "content": "TOOL_RESULT: " + result[:MAX_RESULT_CHARS]})

    summary = {
        "run_id": run_id,
        "stop_reason": stop_reason,
        "steps": step,
        "tool_calls": tool_calls,
        "answer": answer,
        "elapsed_s": round(time.perf_counter() - started, 2),
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
