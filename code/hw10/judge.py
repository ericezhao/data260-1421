# local judge 1-5 (ollama json). set HW10_USE_DEEPEVAL=1 for DeepEval GEval
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw10.config import JUDGE_MODEL, JUDGE_TIMEOUT_SEC, OLLAMA_HOST, SCORE_MAX, SCORE_MIN

CRITERIA = {
    "plan_quality": (
        "Did the Planner make a useful numbered plan for a restaurant-inspection "
        "question? Penalize answering instead of planning."
    ),
    "writer_helpfulness": (
        "Is the Writer draft accurate and useful for the inspection question? "
        "Reward concrete food-safety facts."
    ),
    "final_helpfulness": ("Is the final Reviewer answer helpful and relevant?"),
    "final_vs_draft": ("Did the final improve on the draft? 5=clearly better, 3=similar, 1=worse."),
}


def _clamp(score):
    try:
        s = float(score)
    except Exception:
        s = 3.0
    return max(SCORE_MIN, min(SCORE_MAX, round(s)))


def _ollama_chat(prompt, model=None, timeout=None):
    model = model or JUDGE_MODEL
    timeout = JUDGE_TIMEOUT_SEC if timeout is None else timeout
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 160},
            "messages": [
                {
                    "role": "system",
                    "content": 'Reply JSON only: {"score": <1-5 int>, "reason": "..."}',
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def _do():
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        msg = data.get("message") or {}
        return msg.get("content") or msg.get("thinking") or ""

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_do)
        try:
            return fut.result(timeout=timeout + 5)
        except FuturesTimeout as e:
            raise TimeoutError(f"judge timed out after {timeout}s") from e


def _parse_score_reason(text):
    text = text or ""
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    try:
        start, end = text.find("{"), text.rfind("}")
        obj = json.loads(text[start : end + 1])
        return _clamp(obj.get("score", 3)), str(obj.get("reason") or "")[:400]
    except Exception:
        m = re.search(r"\b([1-5])\b", text)
        return _clamp(m.group(1) if m else 3), text[:200]


def _heuristic_score(name, question, text, other=None):
    # offline / fallback when ollama is down
    t = (text or "").lower()
    score = 3
    reason = "baseline"
    if len(t) < 40:
        score, reason = 2, "too short"
    if any(k in t for k in ("0-100", "inspection", "violation", "sushi", "critical", "grade")):
        score, reason = max(score, 4), "has domain words"
    if name == "final_vs_draft" and other is not None:
        if len(t) > len(other or "") + 20:
            score, reason = 4, "final longer"
        else:
            score, reason = 3, "similar to draft"
    if "plan" in name and ("1." in t and "2." in t):
        score, reason = 4, "numbered plan"
    return _clamp(score), reason


def _score_deepeval(name, criteria, question, actual):
    from deepeval.metrics import GEval
    from deepeval.models.llms.ollama_model import OllamaModel
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    model = OllamaModel(model=JUDGE_MODEL, base_url=OLLAMA_HOST)
    metric = GEval(
        name=name,
        criteria=criteria,
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.5,
    )
    tc = LLMTestCase(input=question or "", actual_output=actual or "")
    metric.measure(tc)
    raw = float(metric.score or 0.5)
    return {
        "name": name,
        "score": _clamp(round(1 + raw * 4)),
        "reason": (metric.reason or "")[:400],
        "engine": "deepeval_geval",
        "raw_0_1": raw,
    }


def score_with_criteria(name, criteria, question, actual, expected=None, mock=None):
    if mock is None:
        mock = os.getenv("HW10_MOCK_JUDGE") == "1"

    # if draft == final, no improvement
    if name == "final_vs_draft" and (actual or "").strip() == (expected or "").strip():
        return {
            "name": name,
            "score": 3,
            "reason": "final same as draft",
            "engine": "same_text",
            "diff": 0,
        }

    if mock:
        s, r = _heuristic_score(name, question, actual, expected)
        return {"name": name, "score": s, "reason": r, "engine": "mock"}

    prompt = (
        f"Criterion: {name}\nRubric: {criteria}\nScore 1-5.\n"
        f"Question:\n{question}\n\nOutput:\n{actual}\n"
    )
    if expected is not None:
        prompt += f"\nCompare to:\n{expected}\n"

    if os.getenv("HW10_USE_DEEPEVAL") == "1":
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_score_deepeval, name, criteria, question, actual)
                return fut.result(timeout=JUDGE_TIMEOUT_SEC + 10)
        except Exception as e:
            print(f"[judge] deepeval failed, fallback ollama: {e}")

    try:
        text = _ollama_chat(prompt)
        s, r = _parse_score_reason(text)
        return {"name": name, "score": s, "reason": r, "engine": "ollama_json"}
    except Exception as e:
        s, r = _heuristic_score(name, question, actual, expected)
        return {
            "name": name,
            "score": s,
            "reason": r + f" | after {type(e).__name__}",
            "engine": "fallback",
            "error": str(e)[:200],
        }
