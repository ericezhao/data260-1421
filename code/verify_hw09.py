# hw9 smoke checks - does not edit app code
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.config import PREFIX, SEED, SID4, VERIFY_SEED

OUT = ROOT / "reports" / "hw09" / "verification.json"


def git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def check(name, ok, detail):
    return {"name": name, "pass": bool(ok), "detail": detail}


def main():
    checks = []
    checks.append(check("prefix", PREFIX == "s1421", f"PREFIX={PREFIX}"))

    # part1 counter
    from hw09.views_cache import InspectionDB

    db = InspectionDB()
    key = db.views_key("ins-001")
    db.redis_client.delete(key)
    db.conn.execute("UPDATE inspections SET view_count = 0 WHERE id = ?", ("ins-001",))
    db.conn.commit()
    last = None
    synced = False
    for _ in range(10):
        last = db.increment_inspection_views("ins-001")
        if last == 10 and db.log_sync_if_needed():
            synced = True
    checks.append(check("part1_incr_to_10", last == 10 and synced, f"last={last}"))
    checks.append(
        check(
            "part1_db_sync",
            db.get_db_view_count("ins-001") == 10,
            f"db={db.get_db_view_count('ins-001')}",
        )
    )
    db.close()

    # files
    hw = ROOT / "reports" / "hw09"
    cases = ROOT / "code" / "hw09" / "cache_cases.yaml"
    checks.append(check("cache_cases_yaml", cases.exists(), str(cases)))
    checks.append(
        check(
            "reports_layout",
            (hw / "METRICS.md").exists() and (hw / "AI_USE.md").exists(),
            str(hw),
        )
    )
    part4 = ROOT / "code" / "hw09" / "part4"
    needed = [
        "reference.json",
        "training_data.json",
        "validation_data.json",
        "test_data.json",
        "lessons.json",
    ]
    checks.append(
        check(
            "part4_datasets",
            all((part4 / n).exists() for n in needed),
            str(part4),
        )
    )

    # semantic cache import
    try:
        from hw09.query_handler import CachedQA
        from hw09.semantic_cache import SemanticResponseCache

        _ = SemanticResponseCache
        _ = CachedQA
        checks.append(check("semantic_modules_import", True, "ok"))
    except Exception as e:
        checks.append(check("semantic_modules_import", False, f"{type(e).__name__}: {e}"))

    failed = [c for c in checks if not c["pass"]]
    payload = {
        "homework": 9,
        "sid4": SID4,
        "commit": git_hash(),
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "total": len(checks),
        },
        "overall_status": "PASS" if not failed else "FAIL",
        "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"overall_status": payload["overall_status"], "summary": payload["summary"]},
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
