from typing import Any, Dict, TypedDict

class AgentState(TypedDict):
    title: str
    content: str
    email: str
    strict: bool
    task: str
    llm: Any
    planner_proposal: Dict[str, Any]
    reviewer_feedback: Dict[str, Any]
    turn_count: int
    planner_attempts: int
    validation_error: str
    max_turns: int
    schema_only: bool
