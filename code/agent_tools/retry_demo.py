"""Part 3 demo: success on attempt 1, success after a retry, and failure after all retries."""

import json
import logging
import sys

from domain_tools import DEFAULT_POLICY, MySQLRepository, run_tool
from faults import ScriptedRepository
from retry import Trace

logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)

SCENARIOS = [
    ("1. success on the first attempt", ["ok"]),
    ("2. failure, then success after a retry", ["error", "ok"]),
    ("3. failure after all allowed retries", ["error", "hang", "error"]),
]


def main():
    policy = DEFAULT_POLICY
    print("Eric Zhao (SID4 1421) - retry policy demo")
    print(
        f"policy: max_attempts={policy.max_attempts}, timeout={policy.timeout_s}s, "
        f"backoff={policy.base_delay_s}s x2 (cap {policy.max_delay_s}s)\n"
    )
    real = MySQLRepository()
    for title, plan in SCENARIOS:
        trace = Trace()
        result = run_tool(
            "get_inspection",
            {"inspection_code": "INS-00042"},
            ScriptedRepository(real, plan),
            policy,
            trace,
        )
        print(f"--- {title}  (plan: {plan})")
        for a in trace.attempts:
            if a["attempt"] > 1:
                print(f"  (backoff {policy.delay_before(a['attempt']):.1f}s)")
            print(f"  attempt {a['attempt']}: {a['outcome']:<52} {a['ms']:>8.1f} ms")
        summary = {"ok": result["ok"], "error": result["error"]}
        if result["ok"]:
            summary["data"] = {k: result["data"][k] for k in ("inspectionCode", "restaurantName", "score")}
        print("  result:", json.dumps(summary), "\n")


if __name__ == "__main__":
    main()
