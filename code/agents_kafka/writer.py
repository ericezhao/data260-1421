# writer: tasks -> drafts
# also does idempotency / retries / dead-letter for part 3
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import (
    DEAD_LETTER_TOPIC,
    DRAFTS_TOPIC,
    KAFKA_BOOTSTRAP,
    TASKS_TOPIC,
)

from agents_kafka.common import ask_model, dumps

SYSTEM = (
    "You are a Writer for restaurant inspections. Using the question and plan, "
    "draft a concise answer (4-6 sentences). If data is missing, say what is "
    "unknown. Do not invent inspection codes."
)

SEEN = set()
MAX_RETRIES = 2


def is_poison(payload):
    return bool(payload.get("poison")) or payload.get("question") == "__POISON__"


async def handle_one(producer, payload, tasks_partition=None):
    correlation_id = payload.get("correlation_id")
    if not correlation_id:
        return False
    if correlation_id in SEEN:
        print(f"[WRITER] idempotent skip correlation_id={correlation_id}")
        return True
    if is_poison(payload):
        raise ValueError("poison message")

    question = payload.get("question", "")
    plan = payload.get("plan", "")
    print(f"[WRITER] drafting correlation_id={correlation_id}")
    draft = ask_model(SYSTEM, f"Question: {question}\nPlan:\n{plan}", num_predict=280)
    out = {
        "correlation_id": correlation_id,
        "question": question,
        "plan": plan,
        "draft": draft,
        "entity_key": payload.get("entity_key") or "general",
        "seq": payload.get("seq"),
        "tasks_partition": tasks_partition,
    }
    await producer.send_and_wait(DRAFTS_TOPIC, dumps(out))
    SEEN.add(correlation_id)
    print(f"[WRITER] sent draft to {DRAFTS_TOPIC}: {draft[:120]!r}")
    return True


async def main():
    consumer = AIOKafkaConsumer(
        TASKS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="s1421-writer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_interval_ms=900_000,
        max_poll_records=1,
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await consumer.start()
    await producer.start()
    print(f"[WRITER] listening on {TASKS_TOPIC} (group=s1421-writer-group)")
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            correlation_id = payload.get("correlation_id")
            retries = int(payload.get("_retries") or 0)
            print(
                f"[WRITER] recv partition={msg.partition} offset={msg.offset} "
                f"key={msg.key!r} correlation_id={correlation_id} retries={retries}"
            )
            try:
                if not correlation_id:
                    print("[WRITER] skip message without correlation_id")
                    await consumer.commit()
                    continue
                ok = await handle_one(producer, payload, tasks_partition=msg.partition)
                if ok:
                    await consumer.commit()
                    print(f"[WRITER] offset committed partition={msg.partition}")
            except Exception as e:
                print(f"[WRITER] failure: {type(e).__name__}: {e}")
                if retries < MAX_RETRIES:
                    payload["_retries"] = retries + 1
                    await producer.send_and_wait(TASKS_TOPIC, dumps(payload), key=msg.key)
                    await consumer.commit()
                    print(f"[WRITER] requeued retry={payload['_retries']}")
                else:
                    dead = {
                        **payload,
                        "dead_letter_reason": str(e),
                        "retries": retries,
                    }
                    await producer.send_and_wait(DEAD_LETTER_TOPIC, dumps(dead))
                    await consumer.commit()
                    print(f"[WRITER] moved to {DEAD_LETTER_TOPIC} correlation_id={correlation_id}")
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
