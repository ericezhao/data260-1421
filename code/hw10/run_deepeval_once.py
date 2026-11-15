#!/usr/bin/env python3
# one DeepEval GEval smoke (optional)
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

os.environ["HW10_USE_DEEPEVAL"] = "1"

from hw10.config import JUDGE_TIMEOUT_SEC, RAW
from hw10.judge import CRITERIA, _score_deepeval


def main():
    timeout = float(os.getenv("HW10_JUDGE_TIMEOUT", str(JUDGE_TIMEOUT_SEC)))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(
                _score_deepeval,
                "writer_helpfulness",
                CRITERIA["writer_helpfulness"],
                "What does a 0-100 inspection score mean?",
                "Inspection scores run from 0 to 100; higher means better food-safety compliance.",
            )
            result = fut.result(timeout=timeout + 15)
    except FuturesTimeout:
        result = {"error": "timeout", "engine": "deepeval"}
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}", "engine": "deepeval"}
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "deepeval_smoke.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
