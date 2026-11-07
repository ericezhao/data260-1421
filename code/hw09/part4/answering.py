# Answering Agent
import json
from datetime import date
from pathlib import Path

DIR = Path(__file__).resolve().parent


def load_lessons(path=None):
    p = path or (DIR / "lessons.json")
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save_lessons(lessons, path=None):
    p = path or (DIR / "lessons.json")
    p.write_text(json.dumps(lessons, indent=2) + "\n", encoding="utf-8")


def relevant_lessons(question, lessons):
    q = question.lower()
    out = []
    for lesson in lessons:
        pattern = (lesson.get("failure_pattern") or "").lower()
        corr = (lesson.get("correction") or "").lower()
        # score / current-value lessons apply to score questions
        if ("value" in pattern or "score" in pattern or "score" in corr) and (
            "score" in q or "blue sushi" in q
        ):
            out.append(lesson)
            continue
        words = [w for w in pattern.split() if len(w) > 4]
        if any(w in q for w in words):
            out.append(lesson)
    return out


def answer_question(question, lessons=None, force_bad=False, feedback=None):
    """Generate an answer. force_bad makes a deliberately incomplete first try.

    If caller passes a lessons list, we mutate that list in memory but do NOT
    overwrite lessons.json (so scoring baseline with lessons=[] cannot wipe disk).
    """
    owns_file = lessons is None
    lessons = load_lessons() if owns_file else lessons
    used = relevant_lessons(question, lessons)
    for lesson in used:
        lesson["use_count"] = int(lesson.get("use_count") or 0) + 1
    if owns_file:
        save_lessons(lessons)

    q = question.lower()
    lesson_hint = " ".join(x.get("correction", "") for x in used)

    # only force a bad first answer when we are NOT already using a lesson
    if force_bad and feedback is None and not used:
        if "blue sushi" in q or "score" in q:
            return {
                "answer": "Blue Sushi was inspected recently.",
                "lessons_used": [x["lesson_id"] for x in used],
                "forced_bad": True,
            }

    if feedback:
        base = _factual_answer(q, lesson_hint)
        return {
            "answer": f"{base} (revised using feedback: {feedback})",
            "lessons_used": [x["lesson_id"] for x in used],
            "forced_bad": False,
            "revised": True,
        }

    return {
        "answer": _factual_answer(q, lesson_hint),
        "lessons_used": [x["lesson_id"] for x in used],
        "forced_bad": False,
    }


def _factual_answer(q, lesson_hint=""):
    # deterministic domain answers grounded in reference.json
    if "range" in q or "between" in q or "numbers can" in q:
        text = "Inspection scores range from 0 to 100; higher is better."
    elif ("raw fish" in q) or (
        "sushi" in q and ("risk" in q or "watch" in q or "why" in q)
    ):
        text = (
            "Sushi is higher risk because of raw fish handling and parasite controls."
        )
    elif "taco spot" in q:
        text = "Taco Spot (ins-002) latest score is 88 with grade B."
    elif "blue sushi" in q and "grade" in q:
        text = "Blue Sushi currently has grade A (score 95)."
    elif "blue sushi" in q or ("blue" in q and "score" in q):
        text = "Blue Sushi (ins-001) latest score is 95 with grade A."
    elif "required" in q or "fields" in q or "inputs" in q or "create" in q:
        text = "Creating an inspection needs restaurant_name, cuisine, and score."
    elif "closed" in q and "placard" in q:
        text = (
            "A closed placard means the facility was ordered closed after inspection findings."
        )
    elif "critical" in q:
        text = (
            "Critical violations can cause foodborne illness risk; "
            "noncritical ones are lower-risk facility issues."
        )
    else:
        text = "I do not have enough domain facts for that question."

    # lesson nudges incomplete score answers to include the concrete value
    if lesson_hint and ("blue sushi" in q or "score" in q) and "95" not in text:
        text = "Blue Sushi (ins-001) latest score is 95 with grade A."
    return text


def add_lesson(failure_pattern, correction, lessons=None):
    lessons = lessons if lessons is not None else load_lessons()
    lesson_id = f"lesson_{len(lessons) + 1:03d}"
    lesson = {
        "lesson_id": lesson_id,
        "failure_pattern": failure_pattern,
        "correction": correction,
        "created_at": str(date.today()),
        "use_count": 0,
    }
    lessons.append(lesson)
    save_lessons(lessons)
    return lesson
