from __future__ import annotations

from typing import Any, Dict, Literal

from .state import AgentState


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    print("[Supervisor] Node activated")
    turn_count = int(state.get("turn_count") or 0) + 1
    print(f"[Supervisor] turn_count={turn_count}")
    return {"turn_count": turn_count}


def _has_issues(feedback: Dict[str, Any]) -> bool:
    data = feedback.get("data") if isinstance(feedback, dict) else {}
    if not isinstance(data, dict):
        return False
    return bool(data.get("issues") or [])


def router_logic(state: AgentState) -> Literal["planner", "reviewer", "END"]:
    max_turns = int(state.get("max_turns") or 10)
    attempts = int(state.get("planner_attempts") or 0)
    error = str(state.get("validation_error") or "").strip()
    proposal = state.get("planner_proposal") or {}
    schema_only = bool(state.get("schema_only"))

    if error or not proposal:
        if attempts >= max_turns:
            return "END"
        return "planner"

    if schema_only:
        return "END"

    feedback = state.get("reviewer_feedback") or {}
    if not feedback:
        return "reviewer"

    if _has_issues(feedback):
        if attempts >= max_turns:
            return "END"
        return "planner"
    return "END"
