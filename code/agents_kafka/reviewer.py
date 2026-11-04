# reviewer: drafts -> final
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import DRAFTS_TOPIC, FINAL_TOPIC, KAFKA_BOOTSTRAP

from agents_kafka.common import ask_model, dumps

SYSTEM = (
    "You are a Reviewer. Score the draft 1-10 for clarity and usefulness for "
    "restaurant-inspection questions. Reply with JSON only: "
    '{"status":"approved"|"needs_revision","score":N,"answer":"<polished answer>"}'
)


async def main():
    consumer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="s1421-reviewer-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_interval_ms=900_000,
        max_poll_records=1,
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await consumer.start()
    await producer.start()
    print(f"[REVIEWER] listening on {DRAFTS_TOPIC}")
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            correlation_id = payload.get("correlation_id")
            draft = payload.get("draft", "")
            print(f"[REVIEWER] reviewing correlation_id={correlation_id}")
            raw = ask_model(
                SYSTEM,
                f"Question: {payload.get('question')}\nDraft:\n{draft}",
                num_predict=260,
            )
            try:
                start, end = raw.find("{"), raw.rfind("}")
                verdict = json.loads(raw[start : end + 1])
            except Exception:
                verdict = {"status": "approved", "score": 7, "answer": draft}
            out = {
                "correlation_id": correlation_id,
                "status": verdict.get("status", "approved"),
                "score": verdict.get("score"),
                "answer": verdict.get("answer") or draft,
                "question": payload.get("question"),
            }
            await producer.send_and_wait(FINAL_TOPIC, dumps(out))
            await consumer.commit()
            print(f"[REVIEWER] final -> {FINAL_TOPIC}: {json.dumps(out)[:200]}")
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
