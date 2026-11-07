# four variants: baseline / evaluator repair / lesson memory / validated improvement
import time
from copy import deepcopy

from hw09.part4.answering import answer_question, load_lessons, save_lessons
from hw09.part4.evaluator import evaluate_answer, load_reference


def run_once(question, variant, lessons=None, force_bad=False):
    """variant in {baseline, evaluator_repair, lesson_memory, validated_improvement}"""
    t0 = time.perf_counter()
    lessons = deepcopy(lessons) if lessons is not None else load_lessons()
    reference = load_reference()
    attempts = 0
    history = []

    use_lessons = variant in {"lesson_memory", "validated_improvement"}
    use_repair = variant in {"evaluator_repair", "lesson_memory", "validated_improvement"}

    active_lessons = lessons if use_lessons else []
    first = answer_question(
        question,
        lessons=active_lessons,
        force_bad=force_bad and attempts == 0,
    )
    attempts = 1
    ev = evaluate_answer(question, first["answer"], reference)
    history.append({"attempt": 1, "answer": first["answer"], "eval": ev, "meta": first})

    final = first
    final_eval = ev

    if use_repair and ev["result"] == "REVISE" and attempts < 2:
        second = answer_question(
            question,
            lessons=active_lessons,
            force_bad=False,
            feedback=ev["feedback"],
        )
        attempts = 2
        ev2 = evaluate_answer(question, second["answer"], reference)
        history.append({"attempt": 2, "answer": second["answer"], "eval": ev2, "meta": second})
        final = second
        final_eval = ev2

        # Do not create lessons here. Lessons are written only in the
        # training/demo path (run_part4), never from held-out test scoring.

    latency_ms = (time.perf_counter() - t0) * 1000
    correct = final_eval["result"] == "PASS"
    return {
        "question": question,
        "variant": variant,
        "final_answer": final["answer"],
        "eval": final_eval,
        "correct": correct,
        "attempts": attempts,
        "latency_ms": latency_ms,
        "history": history,
        "lessons": lessons,
    }


def score_dataset(questions, variant, lessons=None, force_bad_ids=None):
    force_bad_ids = set(force_bad_ids or [])
    rows = []
    lessons_state = deepcopy(lessons) if lessons is not None else load_lessons()
    for item in questions:
        qid = item["id"]
        r = run_once(
            item["question"],
            variant,
            lessons=lessons_state,
            force_bad=qid in force_bad_ids,
        )
        lessons_state = r["lessons"]
        rows.append({"id": qid, **r})
    correct = sum(1 for r in rows if r["correct"])
    incorrect = len(rows) - correct
    avg_attempts = sum(r["attempts"] for r in rows) / len(rows)
    avg_latency = sum(r["latency_ms"] for r in rows) / len(rows)
    return {
        "variant": variant,
        "correct": correct,
        "incorrect": incorrect,
        "average_attempts": round(avg_attempts, 3),
        "average_latency_ms": round(avg_latency, 2),
        "rows": rows,
        "lessons": lessons_state,
    }


def validate_lesson_candidate(before_lessons, candidate_lesson, validation_questions):
    """Keep lesson only if validation does not regress."""
    # score without candidate
    save_lessons(before_lessons)
    before = score_dataset(validation_questions, "lesson_memory", lessons=before_lessons)

    trial = deepcopy(before_lessons) + [candidate_lesson]
    save_lessons(trial)
    after = score_dataset(validation_questions, "lesson_memory", lessons=trial)

    ok = after["correct"] >= before["correct"]
    if ok:
        # persist the scored lesson list (includes use_count bumps)
        save_lessons(after["lessons"])
    else:
        save_lessons(before_lessons)
    return {
        "keep": ok,
        "before_correct": before["correct"],
        "after_correct": after["correct"],
        "before": before,
        "after": after,
    }
