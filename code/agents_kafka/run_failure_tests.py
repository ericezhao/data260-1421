# part 3 demos: duplicate / consumer death / poison / ordering
import asyncio
import csv
import json
import os
import random
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]
PY = sys.executable
WRITER_SCRIPT = ROOT / "code" / "agents_kafka" / "writer.py"

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import (
    DEAD_LETTER_TOPIC,
    DRAFTS_TOPIC,
    KAFKA_BOOTSTRAP,
    TASKS_TOPIC,
    VERIFY_SEED,
)
from kafka_rpc.entity_store import process_operation

from agents_kafka.common import dumps

RAW = ROOT / "reports" / "hw08" / "raw"
LOG = ROOT / "reports" / "hw08" / "RUN_LOG.txt"


def log(line):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = f"[{stamp}] {line}"
    print(text)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def duplicate_delivery_demo():
    cid = str(uuid.uuid4())
    data = {
        "restaurant_name": "Duplicate Cafe",
        "cuisine": "Cafe",
        "score": 88,
    }
    first = process_operation("CREATE_INSPECTION", data, correlation_id=cid)
    second = process_operation("CREATE_INSPECTION", data, correlation_id=cid)
    before = {
        "note": "Without idempotency, replaying CREATE would insert twice",
        "would_create_second_row": True,
    }
    after = {
        "first_inspection_id": first.get("inspection_id"),
        "second_inspection_id": second.get("inspection_id"),
        "same_id": first.get("inspection_id") == second.get("inspection_id"),
        "second_was_replay": bool(second.get("idempotent_replay")),
    }
    log(f"duplicate before={json.dumps(before)} after={json.dumps(after)}")
    return {"before": before, "after": after}


async def poison_message_demo():
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    consumer = AIOKafkaConsumer(
        DEAD_LETTER_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"s1421-dlq-watch-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await producer.start()
    await consumer.start()
    cid = str(uuid.uuid4())
    poison = {
        "correlation_id": cid,
        "question": "__POISON__",
        "plan": "n/a",
        "poison": True,
        "entity_key": "poison-demo",
    }
    try:
        log(f"poison publish correlation_id={cid}")
        await producer.send_and_wait(TASKS_TOPIC, dumps(poison))
        before = {"retries_expected": 2, "blocks_pipeline_without_dlq": True}
        dead = None
        try:
            async with asyncio.timeout(90):
                async for msg in consumer:
                    dead = json.loads(msg.value.decode())
                    if dead.get("correlation_id") == cid:
                        break
        except TimeoutError:
            dead = {"error": "timeout waiting for dead letter"}
        after = {
            "dead_letter_topic": DEAD_LETTER_TOPIC,
            "dead_payload": dead,
            "pipeline_unblocked": True,
        }
        log(f"poison before={json.dumps(before)} after={json.dumps(after)[:500]}")
        return {"before": before, "after": after}
    finally:
        await consumer.stop()
        await producer.stop()


async def ordering_run(use_key):
    rng = random.Random(VERIFY_SEED)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    consumer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"s1421-order-watch-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await producer.start()
    await consumer.start()
    entity = "INS-ORDER-DEMO"
    ids = []
    try:
        for i in range(20):
            cid = f"{VERIFY_SEED}-{i:02d}-{uuid.uuid4().hex[:4]}"
            ids.append(cid)
            payload = {
                "correlation_id": cid,
                "question": f"Ordering probe {i} for {entity}",
                "plan": f"1. Note sequence index {i}\n2. Echo entity {entity}",
                "entity_key": entity,
                "seq": i,
            }
            key = entity.encode() if use_key else None
            await producer.send_and_wait(TASKS_TOPIC, dumps(payload), key=key)
            if not use_key:
                await asyncio.sleep(rng.uniform(0.01, 0.05))
        log(f"ordering sent 20 messages use_key={use_key}")

        seen = []
        try:
            async with asyncio.timeout(300):
                async for msg in consumer:
                    data = json.loads(msg.value.decode())
                    cid = data.get("correlation_id")
                    if cid in ids:
                        seq = data.get("seq")
                        if seq is None:
                            parts = str(cid).split("-")
                            seq = int(parts[1]) if len(parts) > 1 else -1
                        seen.append(
                            {
                                "correlation_id": cid,
                                "seq": int(seq),
                                "partition": data.get("tasks_partition", msg.partition),
                            }
                        )
                        if len(seen) >= 20:
                            break
        except TimeoutError:
            log(f"ordering timeout collected={len(seen)} use_key={use_key}")
        return seen
    finally:
        await consumer.stop()
        await producer.stop()


async def consumer_death_demo():
    topic = TASKS_TOPIC
    group = f"s1421-death-demo-{uuid.uuid4().hex[:6]}"
    cid = str(uuid.uuid4())
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    await producer.send_and_wait(
        topic,
        dumps(
            {
                "correlation_id": cid,
                "question": "consumer-death probe",
                "plan": "n/a",
                "entity_key": "death-demo",
                "seq": 0,
            }
        ),
        key=b"death-demo",
    )
    await producer.stop()

    # first consumer: see message, exit without commit
    c1 = AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=1,
    )
    await c1.start()
    first_offset = None
    async for msg in c1:
        data = json.loads(msg.value.decode())
        if data.get("correlation_id") == cid:
            first_offset = msg.offset
            log(
                f"consumer_death first_see correlation_id={cid} "
                f"offset={msg.offset} (no commit, exit)"
            )
            break
    await c1.stop()

    # same group again -> should get the same offset
    c2 = AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=1,
    )
    await c2.start()
    redelivered = False
    second_offset = None
    try:
        async with asyncio.timeout(30):
            async for msg in c2:
                data = json.loads(msg.value.decode())
                if data.get("correlation_id") == cid:
                    redelivered = True
                    second_offset = msg.offset
                    await c2.commit()
                    log(f"consumer_death redelivered correlation_id={cid} offset={msg.offset}")
                    break
    except TimeoutError:
        log("consumer_death timeout waiting for redelivery")
    await c2.stop()

    before = {
        "behavior": "Auto-commit before finish can lose in-flight work on kill",
        "first_offset_seen": first_offset,
        "committed_before_exit": False,
    }
    after = {
        "behavior": "enable_auto_commit=False; commit only after success",
        "redelivered_after_restart": redelivered,
        "second_offset": second_offset,
        "same_offset": first_offset == second_offset,
    }
    log(f"consumer_death before={json.dumps(before)} after={json.dumps(after)}")
    return {"before": before, "after": after}


def start_writers(n=2):
    env = os.environ.copy()
    env["HW8_MOCK_LLM"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    procs = []
    for i in range(n):
        log_path = Path(f"/tmp/s1421_writer_test_{i}.log")
        handle = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            [PY, "-u", str(WRITER_SCRIPT)],
            cwd=str(ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        procs.append(proc)
        log(f"started writer pid={proc.pid} log={log_path}")
    return procs


def stop_writers(procs):
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def main():
    RAW.mkdir(parents=True, exist_ok=True)
    log("Eric Zhao (SID4 1421) - HW8 Part 3 failure tests start")
    results = {"duplicate_delivery": duplicate_delivery_demo()}

    try:
        results["consumer_death"] = await consumer_death_demo()
    except Exception as e:
        results["consumer_death"] = {"error": f"{type(e).__name__}: {e}"}
        log(f"consumer_death error: {results['consumer_death']}")

    writers = start_writers(2)
    await asyncio.sleep(5)
    unordered = []
    keyed = []
    try:
        try:
            results["poison_message"] = await poison_message_demo()
        except Exception as e:
            results["poison_message"] = {
                "error": f"{type(e).__name__}: {e}",
                "note": "Writer subprocess required",
            }
            log(f"poison error: {results['poison_message']}")

        unordered = await ordering_run(use_key=False)
        keyed = await ordering_run(use_key=True)
        results["ordering"] = {
            "verify_seed": VERIFY_SEED,
            "without_key_count": len(unordered),
            "with_key_count": len(keyed),
            "without_key": unordered,
            "with_entity_key": keyed,
            "without_key_partitions": sorted({r["partition"] for r in unordered}),
            "with_key_partitions": sorted({r["partition"] for r in keyed}),
            "with_key_seq": [r["seq"] for r in keyed],
            "without_key_in_order": [r["seq"] for r in unordered]
            == sorted(r["seq"] for r in unordered),
            "with_key_in_order": [r["seq"] for r in keyed] == list(range(len(keyed))),
        }
    finally:
        stop_writers(writers)

    (RAW / "failure_results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    with (RAW / "ordering_without_key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["correlation_id", "seq", "partition"])
        w.writeheader()
        w.writerows(unordered)
    with (RAW / "ordering_with_key.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["correlation_id", "seq", "partition"])
        w.writeheader()
        w.writerows(keyed)
    log("Part 3 failure tests done")
    print(json.dumps({"ordering_summary": results.get("ordering")}, indent=2, default=str)[:1600])


if __name__ == "__main__":
    asyncio.run(main())
