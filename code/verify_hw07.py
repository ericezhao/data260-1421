"""Smoke test for Homework 7. Writes reports/hw07/verification.json."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "code" / "backend"
TOOLS = ROOT / "code" / "agent_tools"
CODE = ROOT / "code"
HW07 = ROOT / "reports" / "hw07"
OUTPUT = HW07 / "verification.json"
SID4 = 1421
PORT_BASE = 8521
BASE_URL = f"http://127.0.0.1:{PORT_BASE}"
VERIFY_SEED = 261421
LLM_MODEL = "qwen3:8b"

for path in (ROOT, BACKEND, TOOLS, CODE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
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
        [sys.executable, "main.py"],
        cwd=BACKEND,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if server_up():
            return process
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"backend did not start on port {PORT_BASE}")


def token_for(username: str, password: str) -> str:
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        response = client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]


def main() -> None:
    checks = []

    def check(check_id: str, description: str, fn) -> None:
        try:
            evidence = fn()
            checks.append(
                {
                    "id": check_id,
                    "status": "PASS",
                    "description": description,
                    "evidence": evidence,
                }
            )
            print(f"PASS {check_id}")
        except Exception as exc:
            checks.append(
                {
                    "id": check_id,
                    "status": "FAIL",
                    "description": description,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"FAIL {check_id}: {exc}")

    def verify_configuration() -> dict:
        assert PORT_BASE == 8000 + (SID4 % 900)
        assert VERIFY_SEED == 260000 + SID4
        return {"SID4": SID4, "PORT_BASE": PORT_BASE, "VERIFY_SEED": VERIFY_SEED}

    def verify_required_files() -> dict:
        required = [
            BACKEND / "security.py",
            BACKEND / "dependencies.py",
            TOOLS / "agent.py",
            TOOLS / "reflexion.py",
            TOOLS / "file_tools.py",
            CODE / "bike_share" / "tools.py",
            ROOT / ".pre-commit-config.yaml",
            ROOT / "pyproject.toml",
            HW07 / "raw" / "bike" / "hostile_pricing.html",
        ]
        missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
        assert not missing, missing
        return {"files": len(required)}

    def verify_auth() -> dict:
        with httpx.Client(base_url=BASE_URL, timeout=20) as client:
            bad = client.post(
                "/auth/login",
                data={"username": "reader", "password": "wrong"},
            )
            good = client.post(
                "/auth/login",
                data={"username": "reader", "password": "reader123"},
            )
            assert bad.status_code == 401, bad.text
            assert good.status_code == 200 and "access_token" in good.json()
            token = good.json()["access_token"]
            me_ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            me_missing = client.get("/auth/me")
            me_bad = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
            assert me_ok.status_code == 200 and me_ok.json()["role"] == "reader"
            assert me_missing.status_code == 401
            assert me_bad.status_code == 401
        return {"login": 200, "bad_login": 401, "me_role": "reader"}

    def verify_roles() -> dict:
        reader = token_for("reader", "reader123")
        writer = token_for("writer", "writer123")
        moderator = token_for("moderator", "moderator123")
        payload = {
            "restaurantName": "HW7 Role Cafe",
            "cuisine": "Thai",
            "inspectionCode": "INS-98765",
            "score": 95,
            "ownerId": 1,
        }
        with httpx.Client(base_url=BASE_URL, timeout=20) as client:
            listed = client.get(
                "/api/inspections",
                params={"limit": 1},
                headers={"Authorization": f"Bearer {reader}"},
            )
            denied = client.post(
                "/api/inspections",
                json=payload,
                headers={"Authorization": f"Bearer {reader}"},
            )
            created = client.post(
                "/api/inspections",
                json=payload,
                headers={"Authorization": f"Bearer {writer}"},
            )
            assert listed.status_code == 200, listed.text
            assert denied.status_code == 403, denied.text
            assert created.status_code == 201, created.text
            doc_id = created.json()["id"]
            writer_delete = client.delete(
                f"/api/inspections/{doc_id}",
                headers={"Authorization": f"Bearer {writer}"},
            )
            assert writer_delete.status_code == 403, writer_delete.text
            mod_delete = client.delete(
                f"/api/inspections/{doc_id}",
                headers={"Authorization": f"Bearer {moderator}"},
            )
            assert mod_delete.status_code == 204, mod_delete.text
        return {"list": 200, "reader_create": 403, "writer_create": 201, "delete": 204}

    def verify_agent_offline() -> dict:
        from agent import MockModel, run_agent
        from test_tools import FakeRepository

        repo = FakeRepository()
        model = MockModel(
            [
                {
                    "action": "tool",
                    "tool": "search_inspections",
                    "inputs": {"query": "Sushi", "limit": 3},
                },
                {
                    "action": "tool",
                    "tool": "get_inspection",
                    "inputs": {"inspection_code": "INS-00042"},
                },
                {
                    "action": "final",
                    "answer": "Royal Sushi #42 (INS-00042) scored 92.",
                },
            ]
        )
        result = run_agent(
            "Find a sushi place and its score.",
            model=model,
            repo=repo,
            log_path=None,
        )
        assert result["stop_reason"] == "final_answer"
        assert result["tool_calls"] >= 2
        return {"stop_reason": result["stop_reason"], "tool_calls": result["tool_calls"]}

    def verify_bike_and_safety() -> dict:
        from bike_share.make_trips import main as make_trips
        from bike_share.pipeline import run_pipeline
        from file_tools import confirm_bash, is_destructive
        from test_file_safety import integration_debug_search, safety_gate_tests

        make_trips()
        raw = HW07 / "raw" / "bike"
        membership = run_pipeline(
            raw / "membership_wins.csv",
            pricing_url="https://www.lyft.com/bikes/bay-wheels/pricing",
            fixture_text=(raw / "baywheels_pricing_membership.html").read_text(encoding="utf-8"),
        )
        payg = run_pipeline(
            raw / "payg_wins.csv",
            pricing_url="https://www.lyft.com/bikes/bay-wheels/pricing",
            fixture_text=(raw / "baywheels_pricing_payg.html").read_text(encoding="utf-8"),
        )
        assert membership["decision"] == "Buy Monthly Membership"
        assert payg["decision"] == "Pay Per Ride/Minute"
        integration = integration_debug_search()
        assert integration["read_path"] == "beta.py"
        rows = safety_gate_tests()
        assert all(row["ok"] for row in rows)
        assert is_destructive("rm -rf /tmp/x")
        assert confirm_bash("rm -rf /tmp/x")["allowed"] is False
        return {
            "membership": membership["decision"],
            "payg": payg["decision"],
            "safety_rows": len(rows),
        }

    check("configuration", "SID4 / PORT_BASE / VERIFY_SEED", verify_configuration)
    check("required_files", "HW7 modules and lint config exist", verify_required_files)
    server = None
    try:
        server = start_server()
        check(
            "backend_port",
            f"Backend answers on {PORT_BASE}",
            lambda: {"port": PORT_BASE},
        )
        check("auth", "JWT login/me success and 401 paths", verify_auth)
        check(
            "roles",
            "reader/writer/moderator permissions on inspections",
            verify_roles,
        )
    except Exception as exc:
        checks.append(
            {
                "id": "backend_port",
                "status": "FAIL",
                "description": "Backend starts on PORT_BASE",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        print(f"FAIL backend: {exc}")
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

    check(
        "agent_offline",
        "Hand-written agent completes a two-tool MockModel task",
        verify_agent_offline,
    )
    check(
        "bike_and_safety",
        "Bike scenarios decide correctly and safety gate blocks destructive commands",
        verify_bike_and_safety,
    )

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = len(checks) - passed
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 7",
        "homework": 7,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": SID4},
        "llm_model": LLM_MODEL,
        "SEED": SID4,
        "VERIFY_SEED": VERIFY_SEED,
        "overall_status": "PASS" if failed == 0 else "FAIL",
        "summary": {"total_checks": len(checks), "passed": passed, "failed": failed},
        "checks": checks,
    }
    HW07.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"overall_status": payload["overall_status"], "summary": payload["summary"]}, indent=2
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
