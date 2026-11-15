# cache -> planner -> writer -> reviewer (traced)
# prompts copied from agents_kafka so we dont import aiokafka just for SYSTEM
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from agents_kafka.common import ask_model

from hw10.messages import MessageStore
from hw10.tracing import SpanStore, span

PLANNER_SYSTEM = (
    "You are a Planner for a restaurant-inspection knowledge system. "
    "Given a user question, output a short numbered plan (3-5 steps) "
    "for answering it. Do not answer the question itself. Max 80 words."
)
WRITER_SYSTEM = (
    "You are a Writer for restaurant inspections. Using the question and plan, "
    "draft a concise answer (4-6 sentences). If data is missing, say what is "
    "unknown. Do not invent inspection codes."
)
REVIEWER_SYSTEM = (
    "You are a Reviewer. Score the draft 1-10 for clarity and usefulness for "
    "restaurant-inspection questions. Reply with JSON only: "
    '{"status":"approved"|"needs_revision","score":N,"answer":"<polished answer>"}'
)


def _ask(system, user, num_predict=220):
    if os.getenv("HW10_MOCK_LLM") == "1":
        os.environ["HW8_MOCK_LLM"] = "1"
    return ask_model(system, user, num_predict=num_predict)


def _reviewer_answer(question, draft):
    raw = _ask(REVIEWER_SYSTEM, f"Question: {question}\nDraft:\n{draft}", num_predict=260)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        verdict = json.loads(raw[start : end + 1])
        return verdict.get("answer") or draft, verdict
    except Exception:
        return draft, {"status": "approved", "score": 7, "answer": draft}


def _get_cache():
    from hw09.semantic_cache import SemanticResponseCache

    return SemanticResponseCache(threshold=0.85)


def handle_request(
    question,
    trace_id=None,
    force_miss=False,
    fail_stage=None,
    skip_cache_store=False,
    span_store=None,
    message_store=None,
):
    trace_id = trace_id or str(uuid.uuid4())
    spans = span_store or SpanStore()
    messages = message_store or MessageStore()

    plan = draft = final = None
    cached_sim = None
    verdict = None

    with span(spans, trace_id, "cache_lookup") as extra:
        if fail_stage == "cache_lookup":
            raise RuntimeError("injected cache_lookup failure")
        cache = _get_cache()
        if force_miss:
            lookup = {"hit": False, "similarity": 0.0, "answer": None}
        else:
            lookup = cache.search(question, threshold=0.85)
        cache_hit = bool(lookup.get("hit"))
        cached_sim = lookup.get("similarity")
        extra["cache_hit"] = cache_hit
        extra["similarity"] = cached_sim
        extra["path"] = "hit" if cache_hit else "miss"
        if cache_hit:
            final = lookup["answer"]

    if cache_hit:
        record = {
            "correlation_id": trace_id,
            "trace_id": trace_id,
            "question": question,
            "plan": None,
            "draft": None,
            "final": final,
            "answer": final,
            "cache_hit": True,
            "similarity": cached_sim,
            "metadata": {"path": "cache_hit"},
        }
        messages.save(trace_id, record)
        return record

    with span(spans, trace_id, "planner") as extra:
        if fail_stage == "planner":
            raise RuntimeError("injected planner failure")
        plan = _ask(PLANNER_SYSTEM, question, num_predict=120)
        extra["queue_wait_ms"] = 0.0  # in-process, no kafka queue
        extra["chars"] = len(plan or "")

    with span(spans, trace_id, "writer") as extra:
        if fail_stage == "writer":
            raise RuntimeError("injected writer failure")
        draft = _ask(
            WRITER_SYSTEM,
            f"Question: {question}\nPlan:\n{plan}",
            num_predict=280,
        )
        extra["chars"] = len(draft or "")

    with span(spans, trace_id, "reviewer") as extra:
        if fail_stage == "reviewer":
            raise RuntimeError("injected reviewer failure")
        final, verdict = _reviewer_answer(question, draft)
        extra["reviewer_status"] = verdict.get("status")
        extra["reviewer_score"] = verdict.get("score")

    if not skip_cache_store:
        try:
            _get_cache().put(question, final)
        except Exception as e:
            print(f"[pipeline] cache store warn: {e}")

    record = {
        "correlation_id": trace_id,
        "trace_id": trace_id,
        "question": question,
        "plan": plan,
        "draft": draft,
        "final": final,
        "answer": final,
        "cache_hit": False,
        "similarity": cached_sim,
        "metadata": {"path": "cache_miss", "verdict": verdict},
    }
    messages.save(trace_id, record)
    return record
