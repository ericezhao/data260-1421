# join plan/draft/final by correlation_id and score them
import json
import time

from hw10.config import EVAL_RESULTS_DIR
from hw10.judge import CRITERIA, score_with_criteria
from hw10.messages import MessageStore
from hw10.tracing import SpanStore, span


def evaluate_artifact(correlation_id, message_store=None, span_store=None, mock=None):
    messages = message_store or MessageStore()
    spans = span_store or SpanStore()
    stages = messages.load_stages(correlation_id)
    if not stages:
        raise FileNotFoundError(f"no message for {correlation_id}")

    question = stages["question"] or ""
    results = {
        "correlation_id": correlation_id,
        "trace_id": correlation_id,
        "question": question,
        "cache_hit": stages.get("cache_hit"),
        "metrics": {},
        "ts": time.time(),
    }

    with span(spans, correlation_id, "eval") as extra:
        specs = []
        if stages.get("plan"):
            specs.append(("plan_quality", stages["plan"], None))
        if stages.get("draft"):
            specs.append(("writer_helpfulness", stages["draft"], None))
        if stages.get("final"):
            specs.append(("final_helpfulness", stages["final"], None))
        if stages.get("final") and stages.get("draft"):
            specs.append(("final_vs_draft", stages["final"], stages["draft"]))

        for name, actual, expected in specs:
            results["metrics"][name] = score_with_criteria(
                name, CRITERIA[name], question, actual, expected=expected, mock=mock
            )

        extra["n_metrics"] = len(results["metrics"])
        extra["scores"] = {k: v["score"] for k, v in results["metrics"].items()}

    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_RESULTS_DIR / f"{correlation_id}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results["path"] = str(out)
    return results
