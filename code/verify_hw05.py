"""Smoke test for Homework 5. Writes reports/hw05/verification.json.

Starts the backend on PORT_BASE if it is not running, starts both MCP servers over STDIO,
and runs one quick check per part. Temporary records it creates are deleted again.
"""

import asyncio
import csv
import json
import random
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
BACKEND = CODE / "backend"
TOOLS = CODE / "agent_tools"
HW05 = ROOT / "reports" / "hw05"
OUTPUT = HW05 / "verification.json"
SID4 = 1421
PORT_BASE = 8521
BASE_URL = f"http://127.0.0.1:{PORT_BASE}"
VERIFY_SEED = 261421
EMAIL = "eric.zhao@sjsu.edu"
PASSWORD = "password"
LLM_MODEL = "qwen3:8b"

for path in (ROOT, BACKEND, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def server_up() -> bool:
    try:
        httpx.get(f"{BASE_URL}/auth/me", timeout=1)
        return True
    except httpx.HTTPError:
        return False


def start_server() -> subprocess.Popen | None:
    if server_up():
        return None
    process = subprocess.Popen(
        [sys.executable, "main.py"], cwd=BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for _ in range(60):
        if server_up():
            return process
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"backend did not start on port {PORT_BASE}")


@contextmanager
def logged_in_client():
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert resp.status_code == 200, resp.text
        yield client


def call_mcp(server: str, calls: list[tuple[str, dict]]) -> tuple[list[str], list[Any]]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(TOOLS / server)])
        async with stdio_client(params, errlog=open("/dev/null", "w")) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = [t.name for t in (await session.list_tools()).tools]
                results = []
                for name, args in calls:
                    res = await session.call_tool(name, args)
                    structured = res.structuredContent
                    if res.isError:
                        raise RuntimeError(f"{name} returned an error: {res.content[0].text[:200]}")
                    if isinstance(structured, dict) and set(structured) == {"result"}:
                        results.append(structured["result"])
                    elif structured is not None:
                        results.append(structured)
                    else:
                        results.append(json.loads(res.content[0].text))
                return names, results

    return asyncio.run(run())


def main() -> None:
    checks: list[dict[str, Any]] = []
    rng = random.Random(VERIFY_SEED)

    def check(check_id: str, description: str, operation: Callable[[], Any]) -> None:
        try:
            checks.append({"id": check_id, "status": "PASS", "description": description,
                           "evidence": operation()})
        except Exception as error:
            while isinstance(error, ExceptionGroup) and error.exceptions:
                error = error.exceptions[0]
            checks.append({"id": check_id, "status": "FAIL", "description": description,
                           "error": f"{type(error).__name__}: {error}"})

    def verify_configuration() -> dict[str, Any]:
        configuration = {
            "homework": 5,
            "SID4": SID4,
            "PORT_BASE": 8000 + (SID4 % 900),
            "PREFIX": f"s{SID4}",
            "SEED": SID4,
            "VERIFY_SEED": 260000 + SID4,
            "DOMAIN_ID": SID4 % 8,
        }
        assert configuration["PORT_BASE"] == PORT_BASE
        assert configuration["VERIFY_SEED"] == VERIFY_SEED
        return configuration

    def verify_required_files() -> dict[str, Any]:
        required = [
            "code/backend/models.py",
            "code/backend/schema.py",
            "code/backend/crud.py",
            "code/backend/seed.py",
            "code/frontend/src/store.js",
            "code/frontend/src/features/inspectionsSlice.js",
            "code/frontend/dist/index.html",
            "code/agent_tools/meals_server.py",
            "code/agent_tools/domain_server.py",
            "code/agent_tools/domain_tools.py",
            "code/agent_tools/retry.py",
            "code/agent_tools/executor.py",
            "code/agent_tools/agent.py",
            "code/agent_tools/test_tools.py",
            "reports/hw05/RUN_LOG.txt",
            "reports/hw05/METRICS.md",
            "reports/hw05/CONTRACTS.md",
            "reports/hw05/REFLECTION.md",
            "reports/hw05/AI_USE.md",
            "reports/hw05/raw/fault_injection_calls.csv",
            "reports/hw05/raw/fault_injection_summary.csv",
            "reports/hw05/raw/mcp_meals_outputs.json",
            "reports/hw05/raw/mcp_domain_outputs.json",
            "reports/hw05/raw/agent_runs.jsonl",
        ]
        missing = [p for p in required if not (ROOT / p).is_file()]
        assert not missing, f"Missing required files: {missing}"
        return {"required_count": len(required), "missing": []}

    def verify_database_schema() -> dict[str, Any]:
        from sqlalchemy import text
        from database import engine

        with engine.connect() as conn:
            owner_cols = {r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'owners'"))}
            inspection_cols = {r[0] for r in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'inspections'"))}
            uniques = {r[0] for r in conn.execute(text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_schema = DATABASE() AND constraint_type = 'UNIQUE' "
                "AND table_name IN ('owners', 'inspections')"))}
            delete_rule = conn.execute(text(
                "SELECT delete_rule FROM information_schema.referential_constraints "
                "WHERE constraint_schema = DATABASE() AND constraint_name = 'fk_inspections_owner'")).scalar()
            score_default = conn.execute(text(
                "SELECT column_default FROM information_schema.columns WHERE table_schema = DATABASE() "
                "AND table_name = 'inspections' AND column_name = 'score'")).scalar()
            counts = {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                      for t in ("owners", "inspections")}
        assert {"id", "name", "phone", "email", "created_at", "updated_at"} <= owner_cols
        assert {"inspection_code", "score", "owner_id", "created_at", "updated_at"} <= inspection_cols
        assert {"uq_owners_email", "uq_inspections_code"} <= uniques
        assert delete_rule == "RESTRICT", delete_rule
        assert str(score_default) == "100"
        assert counts["owners"] >= 1 and counts["inspections"] >= 1
        return {"unique_constraints": sorted(uniques), "fk_delete_rule": delete_rule,
                "score_default": 100, "row_counts": counts}

    def verify_backend_port() -> dict[str, Any]:
        home = httpx.get(f"{BASE_URL}/", timeout=10)
        assert home.status_code == 200
        blocked = httpx.get(f"{BASE_URL}/api/owners", timeout=10)
        assert blocked.status_code == 401
        return {"port": PORT_BASE, "react_index": 200, "owners_without_login": 401}

    def verify_api() -> dict[str, Any]:
        tag = rng.randint(10000, 99999)
        with logged_in_client() as client:
            page = client.get("/api/owners", params={"skip": 0, "limit": 2})
            assert page.status_code == 200 and len(page.json()) == 2
            owner = client.post("/api/owners", json={
                "name": "Verify Owner", "phone": "408-555-0199", "email": f"verify{tag}@example.com"})
            assert owner.status_code == 201, owner.text
            owner_id = owner.json()["id"]
            inspection_id = None
            try:
                assert client.get(f"/api/owners/{owner_id}").status_code == 200
                assert client.put(f"/api/owners/{owner_id}", json={"phone": "669-555-0199"}).json()["phone"] == "669-555-0199"
                created = client.post("/api/inspections", json={
                    "restaurantName": "Verify Bistro", "cuisine": "French",
                    "inspectionCode": f"INS-{tag}", "ownerId": owner_id})
                assert created.status_code == 201 and created.json()["score"] == 100, created.text
                inspection_id = created.json()["id"]
                updated = client.put(f"/api/inspections/{inspection_id}", json={"score": 77})
                assert updated.status_code == 200 and updated.json()["score"] == 77
                related = client.get(f"/api/owners/{owner_id}/inspections")
                assert [r["id"] for r in related.json()] == [inspection_id]
                errors = {
                    "bad_code_422": client.post("/api/inspections", json={
                        "restaurantName": "X", "cuisine": "X", "inspectionCode": "BAD", "ownerId": owner_id}).status_code,
                    "bad_email_422": client.post("/api/owners", json={
                        "name": "X", "phone": "408-555-0100", "email": "not-an-email"}).status_code,
                    "duplicate_code_409": client.post("/api/inspections", json={
                        "restaurantName": "X", "cuisine": "X", "inspectionCode": f"INS-{tag}", "ownerId": owner_id}).status_code,
                    "missing_owner_404": client.get("/api/owners/99999999").status_code,
                    "delete_owner_with_inspections_409": client.delete(f"/api/owners/{owner_id}").status_code,
                }
                assert errors == {"bad_code_422": 422, "bad_email_422": 422, "duplicate_code_409": 409,
                                  "missing_owner_404": 404, "delete_owner_with_inspections_409": 409}, errors
            finally:
                if inspection_id:
                    assert client.delete(f"/api/inspections/{inspection_id}").status_code == 204
                assert client.delete(f"/api/owners/{owner_id}").status_code == 204
        return {"owner_crud": "201/200/200/204", "inspection_crud": "201/200/204",
                "default_score": 100, "relationship_endpoint": 200, "errors": errors}

    def verify_meals_mcp() -> dict[str, Any]:
        names, (search, empty, details) = call_mcp("meals_server.py", [
            ("search_meals_by_name", {"query": "Arrabiata", "limit": 3}),
            ("search_meals_by_name", {"query": "zzzzqq"}),
            ("meal_details", {"id": "52771"}),
        ])
        assert sorted(names) == sorted(["search_meals_by_name", "meals_by_ingredient", "random_meal", "meal_details"])
        assert search and {"id", "name", "area", "category", "thumb"} <= set(search[0])
        assert empty["results"] == [] and "no matches" in empty["message"]
        assert details["id"] == "52771" and details["ingredients"]
        return {"tools": names, "search_hits": len(search), "empty_message": empty["message"],
                "detail_ingredients": len(details["ingredients"])}

    def verify_domain_mcp() -> dict[str, Any]:
        names, results = call_mcp("domain_server.py", [
            ("search_inspections", {"query": "Sushi", "limit": 3}),
            ("search_inspections", {"query": "S", "limit": 100}),
            ("get_inspection", {"inspection_code": "INS-00042"}),
            ("get_inspection", {"inspection_code": "42"}),
            ("score_summary", {"group_by": "cuisine", "top": 3}),
            ("score_summary", {"group_by": "city"}),
        ])
        assert sorted(names) == ["get_inspection", "score_summary", "search_inspections"]
        for r in results:
            assert set(r) == {"ok", "data", "error"}
        valid, invalid = results[0::2], results[1::2]
        assert all(r["ok"] and r["error"] is None for r in valid)
        assert all(not r["ok"] and r["data"] is None and r["error"] for r in invalid)
        return {"tools": names, "valid_ok": [r["ok"] for r in valid], "invalid_ok": [r["ok"] for r in invalid]}

    def verify_retry_policy() -> dict[str, Any]:
        from domain_tools import run_tool
        from faults import ScriptedRepository
        from retry import RetryPolicy, Trace
        from test_tools import FakeRepository

        policy = RetryPolicy(max_attempts=3, timeout_s=0.5, base_delay_s=0.01, max_delay_s=0.05)
        outcome = {}
        for label, plan in [("first_try", ["ok"]), ("after_retry", ["error", "ok"]),
                            ("exhausted", ["error", "error", "error"])]:
            trace = Trace()
            result = run_tool("get_inspection", {"inspection_code": "INS-00042"},
                              ScriptedRepository(FakeRepository(), plan), policy, trace)
            outcome[label] = {"ok": result["ok"], "attempts": len(trace.attempts)}
        assert outcome == {"first_try": {"ok": True, "attempts": 1},
                           "after_retry": {"ok": True, "attempts": 2},
                           "exhausted": {"ok": False, "attempts": 3}}, outcome
        return outcome

    def verify_fault_injection() -> dict[str, Any]:
        from faults import FlakyRepository
        from retry import TransientError

        class Stub:
            def search(self, *a):
                return []

        def decisions(rate: float) -> list[str]:
            repo = FlakyRepository(Stub(), rate, VERIFY_SEED, hang_s=0)
            for _ in range(50):
                try:
                    repo.search("x", None, 1)
                except TransientError:
                    pass
            return repo.decisions

        sequences = {r: decisions(r) for r in (0.0, 0.2, 0.5)}
        same_seed = all(decisions(r) == seq for r, seq in sequences.items())
        assert same_seed
        assert sequences[0.0].count("ok") == 50 and sequences[0.5].count("ok") < 50
        rows = list(csv.DictReader(open(HW05 / "raw" / "fault_injection_calls.csv")))
        per_rate = {rate: sum(r["failure_rate"] == rate for r in rows) for rate in ("0.0", "0.2", "0.5")}
        assert len(rows) == 150 and set(per_rate.values()) == {50}, per_rate
        summary = list(csv.DictReader(open(HW05 / "raw" / "fault_injection_summary.csv")))
        return {"same_seed_same_sequence": same_seed,
                "injected_failures_in_50": {str(r): 50 - s.count("ok") for r, s in sequences.items()},
                "raw_rows": len(rows), "per_rate": per_rate,
                "success_rates": {s["failure_rate"]: s["success_rate"] for s in summary}}

    def verify_offline_tests() -> dict[str, Any]:
        proc = subprocess.run([sys.executable, "test_tools.py"], cwd=TOOLS, capture_output=True, text=True, timeout=120)
        last = proc.stdout.strip().splitlines()[-1]
        assert proc.returncode == 0, proc.stdout[-500:]
        passed, total = map(int, last.split()[0].split("/"))
        assert passed == total >= 8
        return {"summary": last, "pass_lines": proc.stdout.count("PASS "), "fail_lines": proc.stdout.count("FAIL ")}

    def verify_agent_log() -> dict[str, Any]:
        stops = [json.loads(line) for line in open(HW05 / "raw" / "agent_runs.jsonl")]
        stops = [r for r in stops if r["event"] == "stop"]
        reasons = sorted({r["stop_reason"] for r in stops})
        assert len(stops) >= 4
        assert {"final_answer", "safety_block", "max_steps"} <= set(reasons), reasons
        return {"runs": len(stops), "stop_reasons": reasons}

    def verify_agent_live() -> dict[str, Any]:
        from agent import OllamaModel, run_agent

        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "agent_runs.jsonl"
            result = run_agent("Which cuisine has the lowest average inspection score?",
                               model=OllamaModel(LLM_MODEL), max_steps=5, log_path=log)
            events = [json.loads(line)["event"] for line in log.read_text().splitlines()]
        assert result["stop_reason"] == "final_answer" and result["tool_calls"] >= 1, result
        assert events[0] == "start" and events[-1] == "stop" and "tool_call" in events
        return {"stop_reason": result["stop_reason"], "steps": result["steps"],
                "tool_calls": result["tool_calls"], "logged_events": events}

    check("configuration", "Personal configuration values are correct", verify_configuration)
    check("required_files", "Homework 5 code and report files exist", verify_required_files)
    check("database_schema", "owners/inspections have unique fields, timestamps, score default 100 and a RESTRICT FK",
          verify_database_schema)
    server = None
    try:
        server = start_server()
        check("backend_port", f"Backend answers on port {PORT_BASE} and requires login for /api/owners",
              verify_backend_port)
        check("api", "CRUD for owners and inspections, pagination, relationship endpoint and 404/409/422 errors",
              verify_api)
    except Exception as error:
        checks.append({"id": "backend_port", "status": "FAIL",
                       "description": "Backend starts on PORT_BASE", "error": f"{type(error).__name__}: {error}"})
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
    check("meals_mcp", "meals MCP server starts over STDIO and its tools return the designed shapes", verify_meals_mcp)
    check("domain_mcp", "Domain MCP server returns {ok,data,error} for valid and invalid calls", verify_domain_mcp)
    check("retry_policy", "Retry succeeds first try, succeeds after a retry, and returns a clean error when exhausted",
          verify_retry_policy)
    check("fault_injection", "VERIFY_SEED gives the same failure sequence; 150 raw call records saved",
          verify_fault_injection)
    check("offline_tests", "Offline test runner passes without database, network or LLM", verify_offline_tests)
    check("agent_log", "agent_runs.jsonl has 4+ runs covering final_answer, safety_block and max_steps", verify_agent_log)
    check("agent_live", f"run_agent with {LLM_MODEL} calls a tool and finishes with a final answer", verify_agent_live)

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = len(checks) - passed
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 5",
        "homework": 5,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": SID4},
        "llm_model": LLM_MODEL,
        "SEED": SID4,
        "VERIFY_SEED": VERIFY_SEED,
        "overall_status": "PASS" if failed == 0 else "FAIL",
        "summary": {"total_checks": len(checks), "passed": passed, "failed": failed},
        "checks": checks,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
