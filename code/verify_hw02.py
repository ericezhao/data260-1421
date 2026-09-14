import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
OUTPUT = ROOT / "reports" / "hw02" / "verification.json"
PORT_BASE = 8521
MODEL = "qwen3:8b"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def git_hash() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return process.stdout.strip()


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, description: str, operation: Callable[[], Any]) -> None:
        try:
            evidence = operation()
            checks.append(
                {
                    "id": check_id,
                    "status": "PASS",
                    "description": description,
                    "evidence": evidence,
                }
            )
        except Exception as error:
            checks.append(
                {
                    "id": check_id,
                    "status": "FAIL",
                    "description": description,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    def verify_configuration() -> dict[str, Any]:
        sid4 = 1421
        configuration = {
            "homework": 2,
            "SID4": sid4,
            "PORT_BASE": 8000 + (sid4 % 900),
            "PREFIX": f"s{sid4}",
            "SEED": sid4,
            "VERIFY_SEED": 260000 + sid4,
            "DOMAIN_ID": sid4 % 8,
            "model": MODEL,
        }
        assert configuration["PORT_BASE"] == PORT_BASE
        assert configuration["VERIFY_SEED"] == 261421
        assert configuration["DOMAIN_ID"] == 5
        return configuration

    def verify_required_files() -> dict[str, Any]:
        required = [
            "code/main.py",
            "code/web_application/web_app.html",
            "code/web_application/styles.css",
            "code/web_application/app.js",
            "code/restaurant_graph/state.py",
            "code/restaurant_graph/nodes.py",
            "code/restaurant_graph/router.py",
            "code/restaurant_graph/schema.py",
            "code/restaurant_graph/workflow.py",
            "code/run_hw02_part4.py",
            "src/model_client.py",
            "reports/hw02/cases/schema_input.json",
            "reports/hw02/cases/adversarial_input.json",
            "reports/hw02/raw/schema_runs.json",
            "reports/hw02/raw/ceiling_runs.json",
            "reports/hw02/raw/adversarial_runs.json",
            "reports/hw02/METRICS.md",
            "reports/hw02/RUN_LOG.txt",
            "reports/hw02/AI_USE.md",
            "reports/hw02/reproducible_run_instructions.md",
        ]
        missing = [path for path in required if not (ROOT / path).is_file()]
        assert not missing, f"Missing required files: {missing}"
        return {"required_count": len(required), "missing": []}

    def verify_part1_ui() -> dict[str, Any]:
        html = (CODE / "web_application" / "web_app.html").read_text(encoding="utf-8")
        css = (CODE / "web_application" / "styles.css").read_text(encoding="utf-8")
        assert 'name="viewport"' in html
        assert 'id="loadingMessage"' in html
        assert 'id="emptyMessage"' in html
        assert 'id="errorMessage"' in html
        assert "@media (max-width: 375px)" in css
        return {
            "viewport": True,
            "loading_empty_error": True,
            "mobile_breakpoint": "375px",
        }

    def verify_fastapi_port() -> dict[str, Any]:
        already = port_open(PORT_BASE)
        proc = None
        if not already:
            proc = subprocess.Popen(
                [sys.executable, str(CODE / "main.py")],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(50):
                if port_open(PORT_BASE):
                    break
                time.sleep(0.2)
            else:
                proc.kill()
                raise AssertionError("FastAPI did not start on 8521")
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT_BASE}/api/records", timeout=8
            ) as resp:
                status = resp.status
                payload = json.loads(resp.read().decode())
            assert status == 200
            assert isinstance(payload, list)
            return {
                "port": PORT_BASE,
                "status": status,
                "record_count": len(payload),
                "started_by_verifier": not already,
            }
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def verify_fastapi_crud() -> dict[str, Any]:
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        listed = client.get("/api/records")
        assert listed.status_code == 200
        before = len(listed.json())

        created = client.post(
            "/api/records",
            json={
                "restaurantName": "Verify Cafe",
                "cuisine": "Japanese",
                "Email": "eric.e.zhao@sjsu.edu",
                "Comments": "Smoke-test comments for the homework verifier.",
                "Result": "Pass",
                "termsAccepted": True,
                "submissionDate": "2026-09-14T00:00:00.000Z",
            },
        )
        assert created.status_code == 201
        created_id = created.json()["id"]

        updated = client.put(
            "/api/records/1",
            json={"restaurantName": "Verify Yakitori", "cuisine": "Japanese"},
        )
        assert updated.status_code == 200
        assert updated.json()["restaurantName"] == "Verify Yakitori"

        searched = client.get("/api/records", params={"q": "Verify"})
        assert searched.status_code == 200
        assert any(row["id"] == created_id for row in searched.json())

        deleted = client.delete("/api/records/highest")
        assert deleted.status_code == 204
        after = client.get("/api/records")
        assert after.status_code == 200
        assert all(row["id"] != created_id for row in after.json())
        return {
            "list_ok": True,
            "created_id": created_id,
            "updated_id_1": True,
            "search_ok": True,
            "deleted_highest": True,
            "starting_count": before,
        }

    def verify_model_adapter() -> dict[str, Any]:
        adapter = (ROOT / "src/model_client.py").read_text(encoding="utf-8")
        nodes = (CODE / "restaurant_graph" / "nodes.py").read_text(encoding="utf-8")
        workflow = (CODE / "restaurant_graph" / "workflow.py").read_text(encoding="utf-8")
        assert "def complete(" in adapter
        assert "from src.model_client import OllamaModelClient" in workflow
        assert "llm.complete(" in nodes
        assert "ChatOllama" not in nodes
        assert "ChatOpenAI" not in nodes
        assert "ChatOllama" not in workflow
        return {
            "adapter": "src/model_client.py",
            "consumers": ["code/restaurant_graph/nodes.py", "code/restaurant_graph/workflow.py"],
        }

    def verify_langgraph_finishes() -> dict[str, Any]:
        from src.model_client import OllamaModelClient
        from restaurant_graph.workflow import classify_schema_run, make_state, run_graph

        case = json.loads(
            (ROOT / "reports/hw02/cases/schema_input.json").read_text(encoding="utf-8")
        )
        llm = OllamaModelClient(output_format="json", temperature=0.0)
        state = make_state(
            llm,
            case["title"],
            case["content"],
            case.get("email", "eric.e.zhao@sjsu.edu"),
            max_turns=2,
            schema_only=True,
        )
        final, latency_ms = run_graph(state)
        outcome = classify_schema_run(final)
        data = ((final.get("planner_proposal") or {}).get("data") or {})
        tags = data.get("tags") or []
        assert int(final.get("planner_attempts") or 0) >= 1
        if outcome != "hit_ceiling":
            assert isinstance(tags, list) and len(tags) == 3
        return {
            "finished": True,
            "outcome": outcome,
            "planner_attempts": int(final.get("planner_attempts") or 0),
            "tag_count": len(tags) if isinstance(tags, list) else 0,
            "latency_ms": latency_ms,
        }

    def verify_part4_artifacts() -> dict[str, Any]:
        schema = json.loads(
            (ROOT / "reports/hw02/raw/schema_runs.json").read_text(encoding="utf-8")
        )
        ceiling = json.loads(
            (ROOT / "reports/hw02/raw/ceiling_runs.json").read_text(encoding="utf-8")
        )
        adversarial = json.loads(
            (ROOT / "reports/hw02/raw/adversarial_runs.json").read_text(encoding="utf-8")
        )
        case = json.loads(
            (ROOT / "reports/hw02/cases/schema_input.json").read_text(encoding="utf-8")
        )
        assert schema["input"]["title"] == case["title"]
        assert len(schema["runs"]) == 30
        assert len(ceiling["runs_2"]) == 20
        assert len(ceiling["runs_10"]) == 20
        assert len(adversarial["runs"]) == 5
        return {
            "schema_runs": 30,
            "ceiling_2_runs": 20,
            "ceiling_10_runs": 20,
            "adversarial_runs": 5,
            "schema_counts": schema["summary"]["counts"],
            "adversarial_counts": adversarial["summary"]["counts"],
        }

    check("configuration", "Personal configuration values are correct", verify_configuration)
    check("required_files", "Homework 2 implementation and evidence files exist", verify_required_files)
    check("part1_ui", "List page has viewport, 375px CSS, and loading/empty/error", verify_part1_ui)
    check("fastapi_port", "FastAPI responds on PORT_BASE 8521", verify_fastapi_port)
    check("fastapi_crud", "Record list, create, update id 1, search, and delete highest succeed", verify_fastapi_crud)
    check("model_adapter", "LangGraph nodes call the HW1 model adapter", verify_model_adapter)
    check("langgraph", "LangGraph run finishes and valid output has exactly 3 tags", verify_langgraph_finishes)
    check("part4_results", "Part 4 experiment files match the reported run counts", verify_part4_artifacts)

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = sum(item["status"] == "FAIL" for item in checks)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 2",
        "homework": 2,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": 1421},
        "model": MODEL,
        "SEED": 1421,
        "VERIFY_SEED": 261421,
        "overall_status": "PASS" if failed == 0 else "FAIL",
        "summary": {
            "total_checks": len(checks),
            "passed": passed,
            "failed": failed,
        },
        "checks": checks,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
