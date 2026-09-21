import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
HW03 = ROOT / "reports" / "hw03"
OUTPUT = HW03 / "verification.json"
PORT_BASE = 8521
MODEL = "sentence-transformers/all-MiniLM-L6-v2"

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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            "homework": 3,
            "SID4": sid4,
            "PORT_BASE": 8000 + (sid4 % 900),
            "PREFIX": f"s{sid4}",
            "SEED": sid4,
            "VERIFY_SEED": 260000 + sid4,
            "DOMAIN_ID": sid4 % 8,
            "embedding_model": MODEL,
        }
        assert configuration["PORT_BASE"] == PORT_BASE
        assert configuration["VERIFY_SEED"] == 261421
        assert configuration["DOMAIN_ID"] == 5
        return configuration

    def verify_required_files() -> dict[str, Any]:
        required = [
            "code/main.py",
            "code/auth.py",
            "code/templates/index.html",
            "code/templates/login.html",
            "code/templates/dashboard.html",
            "code/hw03_retrieve.py",
            "reports/hw03/questions.yaml",
            "reports/hw03/SOURCES.md",
            "reports/hw03/CORPUS_MANIFEST.json",
            "reports/hw03/raw/summary.csv",
            "reports/hw03/METRICS.md",
            "reports/hw03/RUN_LOG.txt",
            "reports/hw03/AI_USE.md",
            "README.md",
        ]
        missing = [path for path in required if not (ROOT / path).is_file()]
        assert not missing, f"Missing required files: {missing}"
        return {"required_count": len(required), "missing": []}

    def verify_corpus() -> dict[str, Any]:
        manifest = json.loads((HW03 / "CORPUS_MANIFEST.json").read_text(encoding="utf-8"))
        assert len(manifest) >= 3
        total = 0
        for row in manifest:
            path = HW03 / "corpus" / row["filename"]
            assert path.is_file(), f"missing {row['filename']}"
            size = path.stat().st_size
            assert size == row["byte_size"]
            assert sha256(path) == row["sha256"]
            total += size
        assert total >= 200 * 1024
        sources = (HW03 / "SOURCES.md").read_text(encoding="utf-8")
        assert "http" in sources.lower()
        assert "2026-09-19" in sources
        return {"files": len(manifest), "total_bytes": total}

    def verify_questions() -> dict[str, Any]:
        items = yaml.safe_load((HW03 / "questions.yaml").read_text(encoding="utf-8"))
        assert isinstance(items, list) and len(items) == 5
        sources = []
        for i, item in enumerate(items, 1):
            assert item.get(f"question{i}")
            assert item.get("expected_answer")
            assert item.get("expected_source")
            sources.append(item["expected_source"])
        unique = set(sources)
        assert len(unique) >= 2
        only_one = [name for name in unique if sources.count(name) == 1]
        assert only_one, "at least one question must depend on a single source"
        return {"n_questions": 5, "sources": sorted(unique), "single_source_files": only_one}

    def verify_retrieval_artifacts() -> dict[str, Any]:
        csv_path = HW03 / "raw" / "summary.csv"
        with csv_path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        needed = {
            "technique",
            "q_num",
            "rank",
            "store_score",
            "cosine_sim",
            "chunk_len",
            "preview",
            "latency_ms",
            "source",
            "expected_source",
        }
        assert needed.issubset(set(reader.fieldnames or []))
        assert len(rows) == 75
        techniques = {row["technique"] for row in rows}
        assert techniques == {
            "token-based chunking",
            "semantic chunking",
            "sentence-window chunking",
        }
        metrics = (HW03 / "METRICS.md").read_text(encoding="utf-8")
        for name in techniques:
            assert name in metrics
        for heading in ("Top-1 cosine", "Recall@k", "Mean retrieval latency"):
            assert heading in metrics
        return {"csv_rows": len(rows), "techniques": sorted(techniques)}

    def verify_retrieve_script() -> dict[str, Any]:
        source = (CODE / "hw03_retrieve.py").read_text(encoding="utf-8")
        assert "TokenTextSplitter" in source
        assert "SemanticSplitterNodeParser" in source
        assert "SentenceWindowNodeParser" in source
        assert "IndexFlatIP" in source
        assert "cosine_similarity" in source
        assert "chunk_size=512" in source
        assert "chunk_overlap=50" in source
        return {
            "chunkers": ["token", "semantic", "sentence-window"],
            "vector_store": "faiss IndexFlatIP",
        }

    def verify_auth() -> dict[str, Any]:
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app, base_url="https://testserver")
        home = client.get("/", follow_redirects=False)
        assert home.status_code == 200
        assert b"bootstrap" in home.content.lower() or b"Bootstrap" in home.content
        login = client.get("/login", follow_redirects=False)
        assert login.status_code == 200
        blocked = client.get("/dashboard", follow_redirects=False)
        assert blocked.status_code == 302
        bad = client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=False,
        )
        assert bad.status_code == 302
        assert "/login" in bad.headers.get("location", "")
        ok = client.post(
            "/login",
            data={"username": "admin", "password": "password"},
            follow_redirects=False,
        )
        assert ok.status_code == 302
        assert "/dashboard" in ok.headers.get("location", "")
        cookie = ok.headers.get("set-cookie", "")
        assert "httponly" in cookie.lower()
        assert "samesite=lax" in cookie.lower().replace(" ", "")
        dash = client.get("/dashboard", follow_redirects=False)
        assert dash.status_code == 200
        logout = client.get("/logout", follow_redirects=False)
        assert logout.status_code == 302
        after = client.get("/dashboard", follow_redirects=False)
        assert after.status_code == 302
        auth = (CODE / "auth.py").read_text(encoding="utf-8")
        assert "IDLE_SECONDS = 120" in auth
        return {
            "home": home.status_code,
            "login_ok": True,
            "dashboard_protected": True,
            "logout_clears_session": True,
            "set_cookie_httponly_samesite": True,
        }

    check("configuration", "Personal configuration values are correct", verify_configuration)
    check("required_files", "Homework 3 implementation and evidence files exist", verify_required_files)
    check("corpus", "Corpus files match CORPUS_MANIFEST.json and total at least 200 KB", verify_corpus)
    check("questions", "questions.yaml has five frozen domain questions", verify_questions)
    check("retrieval_artifacts", "summary.csv and METRICS.md cover three techniques", verify_retrieval_artifacts)
    check("retrieve_script", "Retrieve script implements three LlamaIndex chunkers and FAISS", verify_retrieve_script)
    check("auth", "Login, protected dashboard, logout, and session cookie attributes work", verify_auth)

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = sum(item["status"] == "FAIL" for item in checks)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 3",
        "homework": 3,
        "commit_hash": git_hash(),
        "student": {"name": "Eric Zhao", "SID4": 1421},
        "embedding_model": MODEL,
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
