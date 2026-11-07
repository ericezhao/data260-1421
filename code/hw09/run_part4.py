# Part 4 demo: revision, lessons, validation, four variants on test set
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.part4.answering import add_lesson, load_lessons, save_lessons
from hw09.part4.system import run_once, score_dataset, validate_lesson_candidate

DIR = Path(__file__).resolve().parent / "part4"
OUT = ROOT / "reports" / "hw09" / "raw" / "part4_results.json"


def load_json(name):
    return json.loads((DIR / name).read_text(encoding="utf-8"))


def main():
    print("Eric Zhao SID4=1421 Part4 self-improving agents")
    save_lessons([])  # start clean

    training = load_json("training_data.json")
    validation = load_json("validation_data.json")
    test = load_json("test_data.json")

    # 1) controlled revision demo on training question about Blue Sushi score
    demo_q = "What is Blue Sushi's latest score?"
    revision = run_once(demo_q, "evaluator_repair", lessons=[], force_bad=True)

    # 2) create a lesson from that failure pattern and show reuse
    lesson = add_lesson(
        failure_pattern="The answer omits the current value.",
        correction=(
            "Check the reference dataset before answering questions about changing values."
        ),
        lessons=[],
    )
    # validation gate
    gate = validate_lesson_candidate([], lesson, validation)
    print("validation keep=", gate["keep"], gate["before_correct"], "->", gate["after_correct"])

    # later related question: lesson should load and produce a good first answer
    # (force_bad is skipped automatically when a relevant lesson is present)
    reuse = run_once(
        "What score did Blue Sushi get most recently?",
        "lesson_memory",
        lessons=load_lessons(),
        force_bad=True,
    )

    # 3) four variants on the held-out test set (do not mutate test)
    variants = [
        "baseline",
        "evaluator_repair",
        "lesson_memory",
        "validated_improvement",
    ]
    table = []
    details = {}
    lessons_for_test = load_lessons() if gate["keep"] else []
    for v in variants:
        # baseline/evaluator start without lessons; memory variants use kept lessons
        use = lessons_for_test if v in {"lesson_memory", "validated_improvement"} else []
        scored = score_dataset(test, v, lessons=use, force_bad_ids={"te6"})
        table.append(
            {
                "variant": v,
                "correct_answers": scored["correct"],
                "incorrect_answers": scored["incorrect"],
                "average_attempts": scored["average_attempts"],
                "average_latency_ms": scored["average_latency_ms"],
            }
        )
        details[v] = scored

    # persist the kept lessons for submission (do not leave file empty)
    final_lessons = load_lessons() if gate["keep"] else []
    if gate["keep"] and not final_lessons:
        final_lessons = [lesson]
        save_lessons(final_lessons)
    elif gate["keep"]:
        save_lessons(final_lessons)

    payload = {
        "revision_demo": revision,
        "lesson": lesson,
        "validation_gate": {
            "keep": gate["keep"],
            "before_correct": gate["before_correct"],
            "after_correct": gate["after_correct"],
        },
        "lesson_reuse_demo": reuse,
        "results_table": table,
        "training_ids": [x["id"] for x in training],
        "final_lessons": final_lessons,
        "details": {
            k: {"correct": details[k]["correct"], "rows": details[k]["rows"]}
            for k in details
        },
        "notes": {
            "communication": (
                "Answering Agent produces an answer; Evaluator Agent returns "
                "PASS/REVISE + feedback. Max 2 attempts."
            ),
            "lesson_reuse": (
                "Lessons are stored in lessons.json and keyword-matched before answering."
            ),
            "stopping": "Stop after second attempt even if still REVISE.",
            "validation": (
                "A candidate lesson is kept only if validation correct-count does not drop."
            ),
            "limitation": (
                "Keyword lesson matching is brittle; a better approach would embed lessons."
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"table": table, "keep_lesson": gate["keep"]}, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
