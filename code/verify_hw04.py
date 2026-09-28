import csv
import hashlib
import json
import random
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
HW04 = ROOT / "reports" / "hw04"
OUTPUT = HW04 / "verification.json"
SID4 = 1421
PORT_BASE = 8521
BASE_URL = f"http://127.0.0.1:{PORT_BASE}"
VERIFY_SEED = 261421
EMAIL = "eric.zhao@sjsu.edu"
PASSWORD = "password"
LLM_MODEL = "qwen3:8b"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def git_hash() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def server_up() -> bool:
    try:
        httpx.get(f"{BASE_URL}/auth/me", timeout=1)
        return True
    except httpx.HTTPError:
        return False


def start_server() -> subprocess.Popen | None:
    # reuse a server that is already running on PORT_BASE, otherwise start one
    if server_up():
        return None
    process = subprocess.Popen(
        [sys.executable, "main.py"], cwd=CODE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
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


def main() -> None:
    checks: list[dict[str, Any]] = []
    rng = random.Random(VERIFY_SEED)

    def check(check_id: str, description: str, operation: Callable[[], Any]) -> None:
        try:
            checks.append({"id": check_id, "status": "PASS", "description": description,
                           "evidence": operation()})
        except Exception as error:
            checks.append({"id": check_id, "status": "FAIL", "description": description,
                           "error": f"{type(error).__name__}: {error}"})

    def verify_configuration() -> dict[str, Any]:
        configuration = {
            "homework": 4,
            "SID4": SID4,
            "PORT_BASE": 8000 + (SID4 % 900),
            "PREFIX": f"s{SID4}",
            "SEED": SID4,
            "VERIFY_SEED": 260000 + SID4,
            "DOMAIN_ID": SID4 % 8,
        }
        assert configuration["PORT_BASE"] == PORT_BASE
        assert configuration["VERIFY_SEED"] == VERIFY_SEED
        assert configuration["DOMAIN_ID"] == 5
        return configuration

    def verify_required_files() -> dict[str, Any]:
        required = [
            "code/main.py",
            "code/database.py",
            "code/models.py",
            "code/schema.py",
            "code/crud.py",
            "code/session_crud.py",
            "code/seed_hw04.py",
            "code/measure_n1.py",
            "code/rag.py",
            "code/frontend/src/App.jsx",
            "code/frontend/src/pages/Home.jsx",
            "code/frontend/src/pages/Login.jsx",
            "code/frontend/src/pages/CreateRecord.jsx",
            "code/frontend/src/pages/UpdateRecord.jsx",
            "code/frontend/src/pages/DeleteRecord.jsx",
            "code/frontend/dist/index.html",
            "reports/hw04/RUN_LOG.txt",
            "reports/hw04/METRICS.md",
            "reports/hw04/AI_USE.md",
            "reports/hw04/SOURCES.md",
            "reports/hw04/CORPUS_MANIFEST.json",
            "reports/hw04/questions.yaml",
        ]
        missing = [path for path in required if not (ROOT / path).is_file()]
        assert not missing, f"Missing required files: {missing}"
        return {"required_count": len(required), "missing": []}

    def verify_backend_port() -> dict[str, Any]:
        home = httpx.get(f"{BASE_URL}/", timeout=10)
        assert home.status_code == 200
        assert b'<div id="root">' in home.content
        blocked = httpx.get(f"{BASE_URL}/api/inspections/fixed", timeout=10)
        assert blocked.status_code == 401
        return {"port": PORT_BASE, "react_index": home.status_code, "api_without_login": blocked.status_code}

    def verify_auth() -> dict[str, Any]:
        from database import db_session_basede26
        from models import SessionToken

        with httpx.Client(base_url=BASE_URL, timeout=30) as client:
            bad = client.post("/auth/login", json={"email": EMAIL, "password": "wrong"})
            assert bad.status_code == 401
            ok = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
            assert ok.status_code == 200
            set_cookie = ok.headers.get("set-cookie", "").lower()
            assert "httponly" in set_cookie
            token = client.cookies.get("session_id")
            assert token and len(token) == 64 and all(c in "0123456789abcdef" for c in token)
            assert EMAIL not in token
            db = db_session_basede26()
            try:
                assert db.get(SessionToken, token) is not None, "session row missing"
            finally:
                db.close()
            assert client.get("/auth/me").status_code == 200
            assert client.post("/auth/logout").status_code == 200
            assert client.get("/auth/me").status_code == 401
        return {"wrong_password": 401, "cookie_httponly": True, "opaque_token_len": 64,
                "session_row_in_db": True, "me_after_logout": 401}

    def verify_crud() -> dict[str, Any]:
        name = f"Verify Diner {rng.randint(1000, 9999)}"
        with logged_in_client() as client:
            created = client.post("/api/inspections", json={"restaurantName": name, "cuisine": "Thai"})
            assert created.status_code == 201, created.text
            record_id = created.json()["id"]
            try:
                got = client.get(f"/api/inspections/{record_id}")
                assert got.status_code == 200 and got.json()["restaurantName"] == name
                updated = client.put(f"/api/inspections/{record_id}",
                                     json={"restaurantName": name, "cuisine": "Korean"})
                assert updated.status_code == 200 and updated.json()["cuisine"] == "Korean"
            finally:
                deleted = client.delete(f"/api/inspections/{record_id}")
            assert deleted.status_code == 204
            assert client.get(f"/api/inspections/{record_id}").status_code == 404
        return {"create": 201, "read": 200, "update": 200, "delete": 204, "read_after_delete": 404}

    def verify_n_plus_one() -> dict[str, Any]:
        evidence = {}
        with logged_in_client() as client:
            for limit in (10, 50, 200):
                naive = client.get("/api/inspections/naive", params={"limit": limit})
                fixed = client.get("/api/inspections/fixed", params={"limit": limit})
                assert naive.status_code == 200 and fixed.status_code == 200
                assert len(naive.json()) == limit
                assert naive.json() == fixed.json(), "naive and fixed return different data"
                naive_sql = int(naive.headers["X-SQL-Count"])
                fixed_sql = int(fixed.headers["X-SQL-Count"])
                assert naive_sql == limit + 2, naive_sql
                assert fixed_sql == 3, fixed_sql
                evidence[f"limit_{limit}"] = {
                    "records": limit,
                    "with_violations": sum(bool(r["violations"]) for r in fixed.json()),
                    "naive_sql": naive_sql,
                    "fixed_sql": fixed_sql,
                }
        return evidence

    def verify_database() -> dict[str, Any]:
        from sqlalchemy import text

        from database import engine

        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            inspections = conn.execute(text("SELECT COUNT(*) FROM inspections")).scalar()
            violations = conn.execute(text("SELECT COUNT(*) FROM violations")).scalar()
            tables = {row[0] for row in conn.execute(text("SHOW TABLES"))}
            index = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() "
                "AND table_name = 'inspections' AND index_name = 'ix_inspections_cuisine'"
            )).scalar()
            plan = conn.execute(text(
                "EXPLAIN SELECT id, restaurant_name, cuisine FROM inspections WHERE cuisine = 'Thai'"
            )).mappings().first()
        assert db_name == f"s{SID4}_rel"
        assert {"inspections", "violations", "users", "sessions"} <= tables
        assert inspections >= 5000 and violations == 200
        assert index >= 1
        assert plan["key"] == "ix_inspections_cuisine" and plan["type"] == "ref"
        return {"database": db_name, "inspections": inspections, "violations": violations,
                "cuisine_index": True, "explain_type": plan["type"], "explain_key": plan["key"]}

    def verify_n1_artifacts() -> dict[str, Any]:
        rows = list(csv.DictReader((HW04 / "raw" / "n1_requests.csv").open(encoding="utf-8")))
        assert len(rows) == 180
        combos = {}
        for row in rows:
            key = (row["version"], row["page_size"])
            combos[key] = combos.get(key, 0) + 1
        assert set(combos) == {(v, p) for v in ("naive", "fixed") for p in ("10", "50", "200")}
        assert all(count == 30 for count in combos.values())
        summary = list(csv.DictReader((HW04 / "raw" / "n1_summary.csv").open(encoding="utf-8")))
        assert len(summary) == 6
        metrics = (HW04 / "METRICS.md").read_text(encoding="utf-8")
        for heading in ("p50", "p95", "p99", "EXPLAIN"):
            assert heading in metrics
        return {"raw_requests": len(rows), "per_combination": 30, "summary_rows": len(summary)}

    def verify_rag_artifacts() -> dict[str, Any]:
        manifest = json.loads((HW04 / "CORPUS_MANIFEST.json").read_text(encoding="utf-8"))
        assert len(manifest) >= 5
        for row in manifest:
            path = HW04 / "corpus" / row["filename"]
            assert path.stat().st_size == row["byte_size"] and sha256(path) == row["sha256"], row["filename"]
        questions = yaml.safe_load((HW04 / "questions.yaml").read_text(encoding="utf-8"))
        assert [q["id"] for q in questions] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
        assert [q["must_refuse"] for q in questions] == [False] * 4 + [True] * 2
        evals = list(csv.DictReader((HW04 / "raw" / "rag_eval.csv").open(encoding="utf-8")))
        assert len(evals) == 18 and {r["config"] for r in evals} == {"A", "B", "C"}
        refused_c = {r["id"] for r in evals if r["config"] == "C" and r["refused"] == "1"}
        assert {"Q5", "Q6"} <= refused_c
        sweep = list(csv.DictReader((HW04 / "raw" / "rag_k_sweep.csv").open(encoding="utf-8")))
        assert {r["k"] for r in sweep} == {"1", "3", "5"}
        retrievals = (HW04 / "raw" / "rag_retrievals.txt").read_text(encoding="utf-8")
        assert "score=" in retrievals
        assert (HW04 / "raw" / "rag_eval_summary.csv").is_file()
        return {"documents": len(manifest), "questions": 6, "eval_rows": len(evals),
                "config_c_refused": sorted(refused_c), "sweep_k": [1, 3, 5]}

    def verify_rag_live() -> dict[str, Any]:
        import rag
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        from src.model_client import OllamaModelClient

        assert rag.CHUNK_SIZE == 500 and rag.CHUNK_OVERLAP == 50 and rag.TOP_K == 3
        questions = {q["id"]: q for q in yaml.safe_load(rag.QUESTIONS.read_text(encoding="utf-8"))}
        index, per_source = rag.build_index(HuggingFaceEmbedding(model_name=EMBED_MODEL))
        q1_hits = rag.retrieve(index, questions["Q1"]["question"], rag.TOP_K)
        assert q1_hits[0]["source"] == "cors.md"
        assert all({"score", "source", "chunk_id", "text"} <= set(h) for h in q1_hits)

        client = OllamaModelClient(model=LLM_MODEL, num_predict=400)
        answers = {}
        for qid in ("Q1", "Q5", "Q6"):
            hits = rag.retrieve(index, questions[qid]["question"], rag.TOP_K)
            answers[qid] = rag.run_config(client, "C", questions[qid], hits)["answer"]
        assert "600" in answers["Q1"] and rag.CITATION.search(answers["Q1"])
        for qid in ("Q5", "Q6"):
            assert answers[qid].strip().rstrip(".") == rag.REFUSAL, answers[qid]
        return {"chunks": sum(per_source.values()), "q1_top_source": q1_hits[0]["source"],
                "q1_cites_600": True, "q5_refused": True, "q6_refused": True}

    check("configuration", "Personal configuration values are correct", verify_configuration)
    check("required_files", "Homework 4 code and report files exist", verify_required_files)
    server = None
    try:
        server = start_server()
        check("backend_port", f"Backend serves the React app on port {PORT_BASE} and blocks the API without login",
              verify_backend_port)
        check("auth", "Email/password login sets an opaque HTTP-only session cookie stored in the sessions table",
              verify_auth)
        check("crud", "Logged-in user can create, read, update, and delete a record", verify_crud)
        check("n_plus_one", "Naive and fixed list endpoints return the same data at page sizes 10, 50, 200",
              verify_n_plus_one)
    except Exception as error:
        checks.append({"id": "backend_port", "status": "FAIL",
                       "description": "Backend starts on PORT_BASE", "error": f"{type(error).__name__}: {error}"})
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
    check("database", "MySQL has the seeded rows and EXPLAIN uses the cuisine index", verify_database)
    check("n1_artifacts", "180 raw N+1 requests and METRICS.md are present", verify_n1_artifacts)
    check("rag_artifacts", "Corpus, questions, and RAG result files are present and consistent", verify_rag_artifacts)
    check("rag_live", "RAG retrieves the right chunk and config C cites Q1 and refuses Q5/Q6", verify_rag_live)

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = len(checks) - passed
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 4",
        "homework": 4,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": SID4},
        "llm_model": LLM_MODEL,
        "embedding_model": EMBED_MODEL,
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
