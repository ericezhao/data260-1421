"""Offline tests for execute_tool and run_agent: no database, no LLM, no network.

Run:  python code/agent_tools/test_tools.py
"""

import json
import logging
import sys
import traceback

from agent import MockModel, run_agent
from executor import execute_tool
from retry import TransientError

logging.basicConfig(level=logging.CRITICAL)

INSPECTIONS = [
    {"inspectionCode": "INS-00042", "restaurantName": "Royal Sushi #42", "cuisine": "Japanese", "score": 92, "ownerId": 7},
    {"inspectionCode": "INS-00043", "restaurantName": "Blue Sushi #43", "cuisine": "Japanese", "score": 100, "ownerId": 3},
    {"inspectionCode": "INS-00044", "restaurantName": "Lucky Taqueria #44", "cuisine": "Mexican", "score": 84, "ownerId": 7},
]
VIOLATIONS = {"INS-00042": [{"description": "Cold food held above 41F", "severity": "critical"}]}


class FakeRepository:
    """In-memory stand-in for MySQLRepository (dependency injection)."""

    def __init__(self):
        self.calls = 0

    def search(self, query, cuisine, limit):
        self.calls += 1
        rows = [r for r in INSPECTIONS if query.lower() in r["restaurantName"].lower()]
        if cuisine:
            rows = [r for r in rows if r["cuisine"] == cuisine]
        return rows[:limit]

    def get_by_code(self, code):
        self.calls += 1
        row = next((r for r in INSPECTIONS if r["inspectionCode"] == code), None)
        return None if row is None else {**row, "violations": VIOLATIONS.get(code, [])}

    def score_summary(self, group_by, top):
        self.calls += 1
        key = "cuisine" if group_by == "cuisine" else "ownerId"
        groups = {}
        for r in INSPECTIONS:
            groups.setdefault(r[key], []).append(r["score"])
        rows = [
            {"group": g, "inspections": len(s), "avgScore": round(sum(s) / len(s), 2), "minScore": min(s)}
            for g, s in groups.items()
        ]
        return sorted(rows, key=lambda r: r["avgScore"])[:top]


class BrokenRepository(FakeRepository):
    def search(self, query, cuisine, limit):
        self.calls += 1
        raise TransientError("database unavailable")


def call(name, inputs, repo=None):
    raw = execute_tool(name, inputs, repo or FakeRepository())
    assert isinstance(raw, str), "execute_tool must return a JSON string"
    envelope = json.loads(raw)
    assert set(envelope) == {"ok", "data", "error"}, f"bad envelope keys: {set(envelope)}"
    return envelope


# ----- Part 4: one valid and the Part 3 invalid inputs per tool -----
def test_search_valid():
    r = call("search_inspections", {"query": "Sushi", "cuisine": "Japanese", "limit": 5})
    assert r["ok"] and r["error"] is None
    assert r["data"]["count"] == 2


def test_search_invalid_query_and_limit():
    r = call("search_inspections", {"query": "S", "limit": 100})
    assert not r["ok"] and r["data"] is None
    assert "query" in r["error"] and "limit" in r["error"]


def test_detail_valid():
    r = call("get_inspection", {"inspection_code": "INS-00042"})
    assert r["ok"] and r["data"]["restaurantName"] == "Royal Sushi #42"
    assert r["data"]["violations"][0]["severity"] == "critical"


def test_detail_invalid_code_format():
    r = call("get_inspection", {"inspection_code": "42"})
    assert not r["ok"] and "inspection_code" in r["error"]


def test_detail_not_found():
    r = call("get_inspection", {"inspection_code": "INS-99999"})
    assert not r["ok"] and "not found" in r["error"]


def test_summary_valid():
    r = call("score_summary", {"group_by": "cuisine", "top": 2})
    groups = r["data"]["groups"]
    assert r["ok"] and [g["group"] for g in groups] == ["Mexican", "Japanese"]


def test_summary_invalid_group_by():
    r = call("score_summary", {"group_by": "city", "top": 3})
    assert not r["ok"] and "group_by" in r["error"]


def test_unknown_tool_and_bad_json():
    assert "unknown tool" in call("delete_everything", {})["error"]
    assert "not valid JSON" in call("search_inspections", "{oops")["error"]


def test_storage_failure_returns_clean_error():
    repo = BrokenRepository()
    r = call("search_inspections", {"query": "Sushi"}, repo)
    assert not r["ok"] and "after 3 attempts" in r["error"]
    assert repo.calls == 3


# ----- Part 5: safety rule and max_steps -----
def test_safety_rule_blocks_email_lookup():
    repo = FakeRepository()
    r = call("search_inspections", {"query": "maria.lopez@example.com"}, repo)
    assert not r["ok"] and r["data"] is None
    assert r["error"].startswith("blocked by safety rule")
    assert repo.calls == 0, "a blocked call must never reach storage"


def test_run_agent_stops_at_max_steps():
    looping = MockModel([{"action": "tool", "tool": "search_inspections", "inputs": {"query": "Sushi"}}])
    result = run_agent("loop forever", model=looping, max_steps=3, repo=FakeRepository(), log_path=None)
    assert result["stop_reason"] == "max_steps"
    assert result["steps"] == 3 and result["tool_calls"] == 3 and looping.calls == 3
    assert result["answer"] is None


TESTS = [
    test_search_valid,
    test_search_invalid_query_and_limit,
    test_detail_valid,
    test_detail_invalid_code_format,
    test_detail_not_found,
    test_summary_valid,
    test_summary_invalid_group_by,
    test_unknown_tool_and_bad_json,
    test_storage_failure_returns_clean_error,
    test_safety_rule_blocks_email_lookup,
    test_run_agent_stops_at_max_steps,
]


def main() -> int:
    print("Eric Zhao (SID4 1421) - offline tool tests")
    passed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            print(f"FAIL  {test.__name__}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=1, file=sys.stdout)
        else:
            passed += 1
            print(f"PASS  {test.__name__}")
    print(f"\n{passed}/{len(TESTS)} tests passed")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
