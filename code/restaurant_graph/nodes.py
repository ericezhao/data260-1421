from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

_CODE_DIR = Path(__file__).resolve().parent.parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from agents_demo import parse_and_coerce

from .schema import validate_planner_output
from .state import AgentState


def planner_node(state: AgentState) -> Dict[str, Any]:
    print("[Planner] Node activated")
    llm = state["llm"]
    feedback = state.get("reviewer_feedback") or {}
    validation_error = state.get("validation_error") or ""
    attempts = int(state.get("planner_attempts") or 0) + 1

    system_text = (
        "You are Planner. Propose exactly 3 distinct, topical tags "
        "(prefer multi-word phrases) and a one-line summary for the given title and content. "
        "Each tag must be 3-30 characters. Summary must be at most 25 words. "
        "Return only JSON."
    )
    human = (
        f"Task: {state['task']}\n"
        f"Title: {state['title']}\n"
        f"Content: {state['content']}\n"
        f"Reviewer feedback: {json.dumps(feedback, ensure_ascii=False)}\n"
        f"Validation error: {validation_error or 'none'}\n"
        "Return ONLY one JSON object with keys: thought, message, "
        "data.tags (exactly 3 tags, each 3-30 characters), "
        "data.summary (<=25 words), data.issues."
    )

    proposal: Dict[str, Any] = {}
    error_text = ""
    try:
        t0 = time.time()
        response = llm.complete([
            {"role": "system", "content": system_text},
            {"role": "user", "content": human},
        ])
        t1 = time.time()
        print(f"[Planner] latency_ms={int((t1 - t0) * 1000)}")
        proposal, error_text = validate_planner_output(response.content)
        if proposal is None:
            proposal = {"error": error_text, "raw": response.content[:500]}
            print(f"[Planner] schema error: {error_text}")
    except Exception as err:
        print(f"[Planner] ERROR: {err}")
        proposal = {"error": str(err)}
        error_text = str(err)

    print("[Planner] complete")
    return {
        "planner_proposal": proposal or {},
        "reviewer_feedback": {},
        "planner_attempts": attempts,
        "validation_error": error_text,
    }


def reviewer_node(state: AgentState) -> Dict[str, Any]:
    print("[Reviewer] Node activated")
    llm = state["llm"]
    proposal = state.get("planner_proposal") or {}

    system_text = (
        "You are Reviewer. Validate: tags topical and not generic; "
        "summary <= 25 words; no code or markdown. "
        "If issues, list them in data.issues; otherwise echo cleaned tags/summary. "
        "Return only JSON."
    )
    human = (
        f"Task: {state['task']}\n"
        f"Title: {state['title']}\n"
        f"Content: {state['content']}\n"
        f"Planner proposal: {json.dumps(proposal, ensure_ascii=False)}\n"
        "Return ONLY one JSON object with keys: thought, message, "
        "data.tags, data.summary, data.issues."
    )

    feedback: Dict[str, Any] = {}
    try:
        t0 = time.time()
        response = llm.complete([
            {"role": "system", "content": system_text},
            {"role": "user", "content": human},
        ])
        t1 = time.time()
        print(f"[Reviewer] latency_ms={int((t1 - t0) * 1000)}")
        feedback = parse_and_coerce(
            response.content,
            state["title"],
            state["content"],
            state["strict"],
        )
    except Exception as err:
        print(f"[Reviewer] ERROR: {err}")
        feedback = {"error": str(err)}

    print("[Reviewer] complete")
    return {"reviewer_feedback": feedback}
