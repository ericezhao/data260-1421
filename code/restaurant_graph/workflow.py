from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

_CODE_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _CODE_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from langgraph.graph import END, StateGraph

from src.model_client import OllamaModelClient

from .nodes import planner_node, reviewer_node
from .router import router_logic, supervisor_node
from .state import AgentState


def build_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("reviewer", reviewer_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        router_logic,
        {
            "planner": "planner",
            "reviewer": "reviewer",
            "END": END,
        },
    )

    workflow.add_edge("planner", "supervisor")
    workflow.add_edge("reviewer", "supervisor")

    return workflow.compile()


def make_state(
    llm: Any,
    title: str,
    content: str,
    email: str = "eric.e.zhao@sjsu.edu",
    max_turns: int = 10,
    schema_only: bool = False,
) -> AgentState:
    return {
        "title": title,
        "content": content,
        "email": email,
        "strict": False,
        "task": (
            f'Given the title "{title}" and content "{content}", '
            "produce exactly 3 topical tags and a one-sentence summary. "
            f"Email is {email}."
        ),
        "llm": llm,
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "planner_attempts": 0,
        "validation_error": "",
        "max_turns": max_turns,
        "schema_only": schema_only,
    }


def classify_schema_run(final: Dict[str, Any]) -> str:
    error = str(final.get("validation_error") or "").strip()
    proposal = final.get("planner_proposal") or {}
    data = proposal.get("data") if isinstance(proposal, dict) else {}
    valid = (not error) and isinstance(data, dict) and data.get("tags") and data.get("summary")
    attempts = int(final.get("planner_attempts") or 0)
    if not valid:
        return "hit_ceiling"
    if attempts <= 1:
        return "valid_first_attempt"
    if attempts == 2:
        return "valid_after_1_retry"
    return "valid_after_2plus_retries"


def run_graph(initial_state: AgentState) -> Tuple[Dict[str, Any], int]:
    app = build_workflow()
    t0 = time.time()
    final = app.invoke(initial_state, config={"recursion_limit": 50})
    latency_ms = int((time.time() - t0) * 1000)
    return final, latency_ms


def main():
    llm = OllamaModelClient(output_format="json")
    title = "Yakitori Restaurant Inspections"
    content = (
        "Observed multiple live flies landing on clean food-contact storage racks "
        "and food prep counters; small rodent droppings noted near the dry storage "
        "shelving baseboards."
    )
    initial_state = make_state(llm, title, content, max_turns=10, schema_only=False)
    app = build_workflow()
    for event in app.stream(initial_state):
        print(event)


if __name__ == "__main__":
    main()
