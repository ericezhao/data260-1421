# HW8-style planner -> writer -> reviewer path used on cache miss.
# Reuses the same Ollama adapter / mock switch as agents_kafka.
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]


def _ask(system, user, num_predict=220):
    # keep HW8 mock flag so part2/3 timing runs stay cheap
    if os.getenv("HW9_MOCK_LLM") == "1" or os.getenv("HW8_MOCK_LLM") == "1":
        q = user.lower()
        if "sushi" in q and "score" in q:
            return (
                "Inspection scores are 0-100 (higher is better). "
                "Sushi places care because raw fish handling is high risk."
            )
        if "taco" in q or "mexican" in q:
            return "Mexican restaurants often get dinged on hot-holding and handwashing."
        if "grade" in q or "placard" in q:
            return "Public grade placards summarize the latest inspection outcome."
        return (
            "Restaurant inspection scores summarize observed food-safety findings. "
            "Higher scores generally mean fewer / less severe violations."
        )

    # same client HW1/HW8 agents use
    from agents_kafka.common import ask_model

    return ask_model(system, user, num_predict=num_predict)


def run_agent_pipeline(question):
    """Same three roles as HW8 Kafka agents, run in-process for the cache miss path."""
    plan = _ask(
        "You are a Planner for restaurant inspections. Give a short numbered plan.",
        question,
        num_predict=120,
    )
    draft = _ask(
        "You are a Writer for restaurant inspections. Answer using the plan. Be concise.",
        f"Question: {question}\nPlan:\n{plan}",
        num_predict=220,
    )
    final = _ask(
        "You are a Reviewer. Polish the draft into a short final answer. Return answer only.",
        f"Question: {question}\nDraft:\n{draft}",
        num_predict=180,
    )
    return {
        "plan": plan,
        "draft": draft,
        "answer": final,
    }
