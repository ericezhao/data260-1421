import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "reports" / "hw01" / "verification.json"


class HTMLInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locate_ollama() -> str | None:
    command = shutil.which("ollama")
    if command:
        return command
    application_binary = Path("/Applications/Ollama.app/Contents/Resources/ollama")
    return str(application_binary) if application_binary.exists() else None


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
            "SID4": sid4,
            "PORT_BASE": 8000 + (sid4 % 900),
            "PREFIX": f"s{sid4}",
            "SEED": sid4,
            "VERIFY_SEED": 260000 + sid4,
            "DOMAIN_ID": sid4 % 8,
        }
        assert configuration == {
            "SID4": 1421,
            "PORT_BASE": 8521,
            "PREFIX": "s1421",
            "SEED": 1421,
            "VERIFY_SEED": 261421,
            "DOMAIN_ID": 5,
        }
        return configuration

    def verify_required_files() -> dict[str, Any]:
        required = [
            "DOMAIN_SCHEMA.md",
            "code/web_application/web_app.html",
            "code/web_application/styles.css",
            "code/web_application/app.js",
            "code/Dockerfile",
            "code/nginx.conf",
            "code/agents_demo.py",
            "src/model_client.py",
            "code/hw1_client.py",
            "AGENT.md",
            "README.md",
            "reports/hw01/cases/nondeterminism_input.json",
            "reports/hw01/raw/nondeterminism_runs.json",
            "reports/hw01/raw/nondeterminism_runs.csv",
            "reports/hw01/raw/token_turns.json",
            "reports/hw01/METRICS.md",
            "reports/hw01/RUN_LOG.txt",
            "reports/hw01/AI_USE.md",
        ]
        missing = [path for path in required if not (ROOT / path).is_file()]
        assert not missing, f"Missing required files: {missing}"
        return {"required_count": len(required), "missing": []}

    def verify_html() -> dict[str, Any]:
        html_path = ROOT / "code/web_application/web_app.html"
        source = html_path.read_text(encoding="utf-8")
        parser = HTMLInspector()
        parser.feed(source)
        controls = {
            attrs.get("name"): (tag, attrs)
            for tag, attrs in parser.tags
            if tag in {"input", "textarea", "select"} and attrs.get("name")
        }
        assert "<title>HW1-Eric Zhao</title>" in source
        assert any(tag == "h1" for tag, _ in parser.tags)
        assert controls["restaurantID"][1].get("type") == "text"
        assert "required" in controls["restaurantID"][1]
        assert "autofocus" in controls["restaurantID"][1]
        assert controls["restaurantName"][1].get("type") == "text"
        assert "required" in controls["restaurantName"][1]
        assert controls["Email"][1].get("type") == "email"
        assert "required" in controls["Email"][1]
        assert controls["Comments"][0] == "textarea"
        assert "required" in controls["Comments"][1]
        assert controls["Result"][0] == "select"
        assert controls["termsAccepted"][1].get("type") == "checkbox"
        assert "I agree to the terms and conditions." in source
        assert '<script src="app.js"></script>' in source
        categories = [
            "Excellent Pass",
            "Pass",
            "Needs Reinspection",
            "Fail",
        ]
        assert all(f'value="{category}"' in source for category in categories)
        return {
            "file": html_path.name,
            "form_fields": sorted(str(name) for name in controls),
            "category_values": categories,
        }

    def verify_javascript() -> dict[str, Any]:
        source = (ROOT / "code/web_application/app.js").read_text(encoding="utf-8")
        required_patterns = {
            "arrow_validation": r"const\s+validateForm\s*=\s*\(\)\s*=>",
            "length_check": r"length\s*<=\s*25",
            "terms_check": r"!termsCheckbox\.checked",
            "alerts": r"alert\(",
            "json_stringify": r"JSON\.stringify",
            "json_parse": r"JSON\.parse",
            "destructuring": r"const\s*\{\s*restaurantID\s*,\s*Email\s*\}",
            "spread_operator": r"\.\.\.parsedObject",
            "submission_date": r"submissionDate",
            "closure": r"createSubmissionCounter",
        }
        missing = [
            name for name, pattern in required_patterns.items()
            if not re.search(pattern, source)
        ]
        assert not missing, f"Missing JavaScript features: {missing}"
        assert source.count("alert(") >= 2
        return {"verified_features": list(required_patterns)}

    def verify_docker() -> dict[str, Any]:
        dockerfile = (ROOT / "code/Dockerfile").read_text(encoding="utf-8")
        nginx = (ROOT / "code/nginx.conf").read_text(encoding="utf-8")
        assert "FROM nginx:alpine" in dockerfile
        assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile
        assert "EXPOSE 8521" in dockerfile
        assert "listen 8521;" in nginx
        assert "index index.html;" in nginx
        return {"container_port": 8521, "nginx_config_copied": True}

    def verify_python_environment() -> dict[str, Any]:
        version = sys.version_info
        assert (version.major, version.minor) in {(3, 11), (3, 12)}
        return {
            "executable": sys.executable,
            "version": f"{version.major}.{version.minor}.{version.micro}",
        }

    def verify_ollama() -> dict[str, Any]:
        command = locate_ollama()
        assert command, "Ollama executable was not found"
        process = subprocess.run(
            [command, "list"],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        assert "qwen3:8b" in process.stdout
        return {"model": "qwen3:8b", "available": True}

    def verify_model_adapter() -> dict[str, Any]:
        adapter_source = (ROOT / "src/model_client.py").read_text(encoding="utf-8")
        agents_source = (ROOT / "code/agents_demo.py").read_text(encoding="utf-8")
        client_source = (ROOT / "code/hw1_client.py").read_text(encoding="utf-8")
        compile(adapter_source, "src/model_client.py", "exec")
        compile(agents_source, "code/agents_demo.py", "exec")
        compile(client_source, "code/hw1_client.py", "exec")
        assert "def complete(" in adapter_source
        assert "from src.model_client import OllamaModelClient" in agents_source
        assert "from src.model_client import OllamaModelClient" in client_source
        assert "ChatOllama" not in agents_source
        assert "ChatOllama" not in client_source
        return {
            "adapter": "src/model_client.py",
            "consumers": ["code/agents_demo.py", "code/hw1_client.py"],
        }

    def verify_part3_results() -> dict[str, Any]:
        case_path = ROOT / "reports/hw01/cases/nondeterminism_input.json"
        raw_path = ROOT / "reports/hw01/raw/nondeterminism_runs.json"
        csv_path = ROOT / "reports/hw01/raw/nondeterminism_runs.csv"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        results = payload["results"]
        assert case["title"] == "Yakitori Restaurant Inspections"
        assert payload["input_sha256"] == sha256(case_path)
        assert len(results) == 40
        assert sum(result["temperature"] == 0.7 for result in results) == 20
        assert sum(result["temperature"] == 0.0 for result in results) == 20
        assert all(len(result["tags"]) == 3 for result in results)
        with csv_path.open(newline="", encoding="utf-8") as stream:
            csv_rows = list(csv.DictReader(stream))
        assert len(csv_rows) == 40
        return {
            "input_sha256": payload["input_sha256"],
            "total_runs": 40,
            "temperature_0_7_runs": 20,
            "temperature_0_0_runs": 20,
            "csv_rows": 40,
        }

    def verify_part4_results() -> dict[str, Any]:
        payload = json.loads(
            (ROOT / "reports/hw01/raw/token_turns.json").read_text(encoding="utf-8")
        )
        turns = payload["turn_records"]
        snapshots = payload["stats_snapshots"]
        assert len(turns) == 5
        assert all(turn["bullet_only"] for turn in turns)
        assert [snapshot["turn_count"] for snapshot in snapshots] == [3, 5]
        assert all(
            later["input_tokens"] > earlier["input_tokens"]
            for earlier, later in zip(turns, turns[1:])
        )
        assert payload["final_stats"]["cumulative_input_tokens"] == sum(
            turn["input_tokens"] for turn in turns
        )
        assert payload["final_stats"]["cumulative_output_tokens"] == sum(
            turn["output_tokens"] for turn in turns
        )
        return {
            "turn_count": 5,
            "bullet_only_passes": 5,
            "stats_after_turns": [3, 5],
            "cumulative_input_tokens": payload["final_stats"]["cumulative_input_tokens"],
            "cumulative_output_tokens": payload["final_stats"]["cumulative_output_tokens"],
            "final_serialized_history_length_bytes": payload["final_stats"][
                "serialized_history_length_bytes"
            ],
        }

    check("configuration", "Personal configuration values are correct", verify_configuration)
    check("required_files", "Core implementation and evidence files exist", verify_required_files)
    check("html_form", "HTML form satisfies Part 1 field requirements", verify_html)
    check("javascript", "JavaScript contains all required ES6 behaviors", verify_javascript)
    check("docker", "Docker and Nginx use PORT_BASE 8521", verify_docker)
    check("python", "Python version is 3.11 or 3.12", verify_python_environment)
    check("ollama", "Ollama has the qwen3:8b model available", verify_ollama)
    check("model_adapter", "All active Python model calls use the adapter", verify_model_adapter)
    check("part3_results", "Part 3 contains 40 valid fixed-input runs", verify_part3_results)
    check("part4_results", "Part 4 contains five turns and two stats snapshots", verify_part4_results)

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = sum(item["status"] == "FAIL" for item in checks)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "DATA-260 Homework 1",
        "student": {"name": "Eric Zhao", "SID4": 1421},
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
