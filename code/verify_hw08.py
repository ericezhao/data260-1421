# hw8 smoke checks - does not edit app code
import asyncio
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import (
    KAFKA_BOOTSTRAP,
    PREFIX,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
    SEED,
    SID4,
    TIMEOUT_SECONDS,
    VERIFY_SEED,
)
from kafka_rpc.entity_store import INSPECTIONS, PROCESSED, process_operation

OUT = ROOT / "reports" / "hw08" / "verification.json"


def git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def check(name, ok, detail):
    return {"name": name, "pass": bool(ok), "detail": detail}


async def kafka_create_get():
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    consumer = AIOKafkaConsumer(
        RESPONSE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"s1421-verify-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await producer.start()
    await consumer.start()

    async def once(operation, data):
        correlation_id = str(uuid.uuid4())
        message = {
            "correlation_id": correlation_id,
            "reply_to": RESPONSE_TOPIC,
            "operation": operation,
            "data": data,
        }
        await producer.send_and_wait(REQUEST_TOPIC, json.dumps(message).encode())
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for msg in consumer:
                payload = json.loads(msg.value.decode())
                if payload.get("correlation_id") == correlation_id:
                    return payload
        raise TimeoutError(operation)

    try:
        created = await once(
            "CREATE_INSPECTION",
            {
                "restaurant_name": "Verify Kafka Sushi",
                "cuisine": "Japanese",
                "score": 93,
            },
        )
        iid = created.get("inspection_id")
        fetched = await once("GET_INSPECTION", {"inspection_id": iid})
        return {"created": created, "fetched": fetched}
    finally:
        await consumer.stop()
        await producer.stop()


def main():
    checks = []
    checks.append(check("prefix_topics", PREFIX == "s1421", f"PREFIX={PREFIX}"))

    INSPECTIONS.clear()
    PROCESSED.clear()
    cid = str(uuid.uuid4())
    created = process_operation(
        "CREATE_INSPECTION",
        {"restaurant_name": "Verify Sushi", "cuisine": "Japanese", "score": 91},
        correlation_id=cid,
    )
    checks.append(
        check(
            "create_inspection_local",
            created.get("success") is True and "inspection_id" in created,
            json.dumps(created),
        )
    )
    iid = created.get("inspection_id")
    fetched = process_operation(
        "GET_INSPECTION", {"inspection_id": iid}, correlation_id=str(uuid.uuid4())
    )
    checks.append(
        check(
            "get_inspection_local",
            fetched.get("success") is True
            and (fetched.get("entity") or {}).get("inspection_id") == iid,
            json.dumps(fetched),
        )
    )
    again = process_operation(
        "CREATE_INSPECTION",
        {"restaurant_name": "Verify Sushi", "cuisine": "Japanese", "score": 91},
        correlation_id=cid,
    )
    checks.append(
        check(
            "idempotent_create_replay",
            again.get("inspection_id") == iid and again.get("idempotent_replay") is True,
            json.dumps(again),
        )
    )
    bad = process_operation("DELETE_INSPECTION", {})
    checks.append(
        check(
            "unknown_operation",
            bad.get("success") is False and "Unknown" in str(bad.get("error")),
            json.dumps(bad),
        )
    )
    missing = process_operation("GET_INSPECTION", {"inspection_id": "nope"})
    checks.append(check("missing_entity", missing.get("success") is False, json.dumps(missing)))

    try:
        kafka_result = asyncio.run(kafka_create_get())
        kc = kafka_result["created"]
        kf = kafka_result["fetched"]
        ok = (
            kc.get("success") is True
            and kf.get("success") is True
            and (kf.get("entity") or {}).get("inspection_id") == kc.get("inspection_id")
        )
        checks.append(check("kafka_create_get_roundtrip", ok, json.dumps(kafka_result)[:800]))
    except Exception as e:
        checks.append(check("kafka_create_get_roundtrip", False, f"{type(e).__name__}: {e}"))

    try:
        import agents_kafka.planner  # noqa: F401
        import agents_kafka.reviewer  # noqa: F401
        import agents_kafka.writer  # noqa: F401

        checks.append(check("agent_modules_import", True, "ok"))
    except Exception as e:
        checks.append(check("agent_modules_import", False, f"{type(e).__name__}: {e}"))

    hw08 = ROOT / "reports" / "hw08"
    raw = hw08 / "raw"
    checks.append(
        check(
            "reports_hw08_layout",
            (hw08 / "METRICS.md").exists() and (hw08 / "AI_USE.md").exists(),
            str(hw08),
        )
    )
    checks.append(
        check(
            "part3_raw_artifacts",
            (raw / "failure_results.json").exists()
            and (raw / "ordering_without_key.csv").exists()
            and (raw / "ordering_with_key.csv").exists(),
            str(raw),
        )
    )

    failed = [c for c in checks if not c["pass"]]
    payload = {
        "homework": 8,
        "sid4": SID4,
        "commit": git_hash(),
        "model": "qwen3:8b",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "kafka_bootstrap": KAFKA_BOOTSTRAP,
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
            {"overall_status": payload["overall_status"], "summary": payload["summary"]}, indent=2
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
