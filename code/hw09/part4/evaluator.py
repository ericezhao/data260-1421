# Evaluator Agent - checks answers against reference.json ground truth
import json
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent


def load_reference(path=None):
    p = path or (DIR / "reference.json")
    return json.loads(p.read_text(encoding="utf-8"))


def _pick_facts(question, reference):
    """Map a question to the reference facts it should cover."""
    q = question.lower()
    facts = reference.get("facts") or []
    by_topic = {f["topic"]: f for f in facts}
    picked = []

    if "range" in q or "between" in q or "numbers" in q:
        picked.append(by_topic.get("score_range"))
    if ("raw fish" in q) or (
        "sushi" in q and ("risk" in q or "watch" in q or "why" in q)
    ):
        picked.append(by_topic.get("sushi_risk"))
    if "taco spot" in q:
        picked.append(by_topic.get("taco_spot_score"))
    if "blue sushi" in q or ("blue" in q and ("score" in q or "grade" in q)):
        picked.append(by_topic.get("blue_sushi_score"))
    if "required" in q or "fields" in q or "inputs" in q or "create" in q:
        picked.append(by_topic.get("create_fields"))
    if "closed" in q and "placard" in q:
        picked.append(by_topic.get("placard_closed"))
    if "critical" in q:
        picked.append(by_topic.get("critical_vs_noncritical"))

    out = []
    seen = set()
    for f in picked:
        if f and f["id"] not in seen:
            out.append(f)
            seen.add(f["id"])
    return out


def _required_snippets(fact, question):
    q = question.lower()
    topic = fact["topic"]
    if topic == "score_range":
        return ["0", "100"]
    if topic == "sushi_risk":
        return ["raw fish"]
    if topic == "blue_sushi_score":
        # grade questions can pass with grade A; score questions need 95
        if "grade" in q and "score" not in q:
            return ["grade a"]
        return ["95"]
    if topic == "taco_spot_score":
        return ["88"]
    if topic == "create_fields":
        return ["restaurant_name", "cuisine", "score"]
    if topic == "placard_closed":
        return ["closed"]
    if topic == "critical_vs_noncritical":
        return ["critical"]
    words = [w for w in re.findall(r"[a-z0-9_]+", fact["text"].lower()) if len(w) > 3]
    return words[:2]


def evaluate_answer(question, answer, reference=None):
    reference = reference or load_reference()
    ans = (answer or "").lower()
    # normalize so "grade A" matches required "grade a"
    facts = _pick_facts(question, reference)

    if not facts:
        return {
            "result": "REVISE",
            "explanation": "No matching reference fact for this question.",
            "feedback": "Only answer using facts from the reference dataset.",
            "missing": [],
            "facts_used": [],
        }

    missing = []
    for fact in facts:
        for snip in _required_snippets(fact, question):
            if snip.lower() not in ans:
                missing.append(snip)

    if missing:
        return {
            "result": "REVISE",
            "explanation": "Answer is missing required reference facts.",
            "feedback": "Include these missing facts: " + ", ".join(missing),
            "missing": missing,
            "facts_used": [f["id"] for f in facts],
        }

    return {
        "result": "PASS",
        "explanation": "Answer covers the reference facts for this question.",
        "feedback": "",
        "missing": [],
        "facts_used": [f["id"] for f in facts],
    }
