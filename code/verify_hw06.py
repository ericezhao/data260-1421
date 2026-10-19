"""Smoke test for Homework 6. Writes reports/hw06/verification.json.

Starts the backend on PORT_BASE when it is not already running. It creates one
temporary inspection document and deletes it. It does not rewrite MEMORY.md.
"""

import inspect
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "code" / "backend"
HW06 = ROOT / "reports" / "hw06"
OUTPUT = HW06 / "verification.json"
SID4 = 1421
PORT_BASE = 8521
BASE_URL = f"http://127.0.0.1:{PORT_BASE}"
VERIFY_SEED = 261421
LLM_MODEL = "qwen3:8b"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


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


def main() -> None:
    checks = []

    def check(check_id: str, description: str, fn) -> None:
        try:
            evidence = fn()
            checks.append({"id": check_id, "status": "PASS", "description": description, "evidence": evidence})
            print(f"PASS {check_id}")
        except Exception as exc:
            checks.append({
                "id": check_id,
                "status": "FAIL",
                "description": description,
                "error": f"{type(exc).__name__}: {exc}",
            })
            print(f"FAIL {check_id}: {exc}")

    def verify_configuration() -> dict:
        assert SID4 == 1421
        assert PORT_BASE == 8000 + (SID4 % 900)
        assert VERIFY_SEED == 260000 + SID4
        from mongo_config import settings
        assert settings.MONGODB_DB == "s1421_doc"
        return {"SID4": SID4, "PORT_BASE": PORT_BASE, "database": settings.MONGODB_DB}

    def verify_required_files() -> dict:
        required = [
            ROOT / "AGENT.md",
            ROOT / "MEMORY.md",
            HW06 / "memory_probes.yaml",
            HW06 / "MEMORY_original.md",
            HW06 / "MEMORY_consolidated.md",
            BACKEND / "documents.py",
            BACKEND / "chat_api.py",
            BACKEND / "memory_store.py",
            BACKEND / "file_memory.py",
            BACKEND / "score_label.py",
        ]
        missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
        assert not missing, missing
        agent = (ROOT / "AGENT.md").read_text(encoding="utf-8")
        project = agent.split("# Project instructions", 1)[1]
        bullets = [line for line in project.splitlines() if line.startswith("- ")]
        assert len(bullets) >= 5, len(bullets)
        return {"files": len(required), "project_instructions": len(bullets)}

    def verify_score_label() -> dict:
        from score_label import inspection_score_label

        source = inspect.getsource(inspection_score_label)
        assert "print(" not in source
        assert "score: int" in source and "-> str" in source
        assert '"""' in source
        assert inspection_score_label(95) == "good"
        assert inspection_score_label(70) == "fair"
        assert inspection_score_label(69) == "poor"
        try:
            inspection_score_label(101)
        except ValueError:
            pass
        else:
            raise AssertionError("101 should raise ValueError")
        try:
            inspection_score_label(-1)
        except ValueError:
            pass
        else:
            raise AssertionError("-1 should raise ValueError")
        return {"label_95": "good", "rejects_out_of_range": True}

    def verify_consolidation() -> dict:
        from file_memory import consolidate_memory, content_line_count

        original = (HW06 / "MEMORY_original.md").read_text(encoding="utf-8")
        updated, before, after = consolidate_memory(original)
        assert len(original.splitlines()) == 55
        assert before > 40 and after < 40, (before, after)
        assert "- port_base: 8000" in updated
        assert "- resolved port_base:" in updated
        assert "- repo_owner: Eric Zhao" in updated
        assert updated.count("- repo_owner:") == 1
        saved = content_line_count((HW06 / "MEMORY_consolidated.md").read_text(encoding="utf-8"))
        assert saved < 40
        return {"content_before": before, "content_after": after, "saved_file_content_lines": saved}

    def verify_documents() -> dict:
        with httpx.Client(base_url=BASE_URL, timeout=20) as client:
            missing = client.post("/api/documents", json={
                "restaurantName": "Missing Cuisine",
                "inspectedAt": "2026-10-18T16:00:00Z",
            })
            bad_enum = client.post("/api/documents", json={
                "restaurantName": "Bad Cuisine",
                "cuisine": "Martian",
                "inspectedAt": "2026-10-18T16:00:00Z",
            })
            bad_json = client.post(
                "/api/documents",
                content='{"restaurantName": ',
                headers={"Content-Type": "application/json"},
            )
            bad_id = client.get("/api/documents/not-an-id")
            created = client.post("/api/documents", json={
                "restaurantName": "Verify Grill",
                "notes": "temporary verify row",
                "cuisine": "Thai",
                "inspectedAt": "2026-10-18T16:00:00Z",
                "violations": [{"description": "No soap", "severity": "minor"}],
            })
            assert created.status_code == 201, created.text
            doc_id = created.json()["id"]
            assert created.json()["status"] == "open"
            fetched = client.get(f"/api/documents/{doc_id}")
            updated = client.put(f"/api/documents/{doc_id}", json={"status": "closed", "score": 88})
            deleted = client.delete(f"/api/documents/{doc_id}")
            gone = client.get(f"/api/documents/{doc_id}")
        assert missing.status_code == 422, missing.text
        assert bad_enum.status_code == 422, bad_enum.text
        assert bad_json.status_code == 400, bad_json.text
        assert bad_id.status_code == 400, bad_id.text
        assert fetched.status_code == 200 and fetched.json()["cuisine"] == "Thai"
        assert updated.status_code == 200 and updated.json()["status"] == "closed"
        assert deleted.status_code == 204
        assert gone.status_code == 404
        return {"created": doc_id, "validation": [missing.status_code, bad_enum.status_code, bad_json.status_code]}

    def verify_commands() -> dict:
        with httpx.Client(base_url=BASE_URL, timeout=20) as client:
            response = client.post("/api/chat", json={"user_id": "verify-hw06", "message": "/help"})
        assert response.status_code == 200, response.text
        reply = response.json()["reply"]
        for command in ("/memory", "/compact", "/dream", "/help"):
            assert command in reply
        return {"commands": 4}

    def verify_chat() -> dict:
        with httpx.Client(base_url=BASE_URL, timeout=180) as client:
            response = client.post("/api/chat", json={
                "user_id": "verify-hw06",
                "session_id": "verify-session",
                "message": "Say hello in one short sentence.",
                "short_term_n": 4,
            })
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["reply"].strip()
            used = body["memory_used"]
            assert used["short_term_count"] >= 1
            assert "episodes" in used
            memory = client.get("/api/memory/verify-hw06")
            aggregate = client.get("/api/aggregate/verify-hw06")
        assert memory.status_code == 200 and memory.json()["messages"]
        assert aggregate.status_code == 200 and aggregate.json()["daily_counts"]
        usage = body["usage"]
        assert "prompt_tokens" in usage and "latency_ms" in usage
        return {
            "reply_chars": len(body["reply"]),
            "short_term_count": used["short_term_count"],
            "prompt_tokens": usage["prompt_tokens"],
            "daily_rows": len(aggregate.json()["daily_counts"]),
        }

    check("configuration", "SID4, PORT_BASE, VERIFY_SEED, and the s1421_doc database name", verify_configuration)
    check("required_files", "HW6 files exist and AGENT.md has at least five project instructions", verify_required_files)
    check("score_label", "inspection_score_label follows the AGENT.md type, docstring, and range rules", verify_score_label)
    check("consolidation", "The 55-line MEMORY.md consolidates to under 40 content lines and records conflicts", verify_consolidation)
    server = None
    try:
        server = start_server()
        check("backend_port", f"Backend answers on port {PORT_BASE}", lambda: {"port": PORT_BASE, "started_by_verify": server is not None})
        check("documents", "MongoDB document CRUD, 400 for bad JSON or id, 404, and 422 for bad fields", verify_documents)
        check("commands", "/help lists /memory, /compact, /dream, and /help", verify_commands)
        check("chat", "POST /api/chat returns a reply plus memory_used, and the memory and aggregate routes respond", verify_chat)
    except Exception as exc:
        checks.append({
            "id": "backend_port",
            "status": "FAIL",
            "description": "Backend starts on PORT_BASE",
            "error": f"{type(exc).__name__}: {exc}",
        })
        print(f"FAIL backend: {exc}")
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = len(checks) - passed
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 6",
        "homework": 6,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": SID4},
        "llm_model": LLM_MODEL,
        "SEED": SID4,
        "VERIFY_SEED": VERIFY_SEED,
        "overall_status": "PASS" if failed == 0 else "FAIL",
        "summary": {"total_checks": len(checks), "passed": passed, "failed": failed},
        "checks": checks,
    }
    HW06.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall_status": payload["overall_status"], "summary": payload["summary"]}, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
