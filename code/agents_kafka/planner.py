# planner: inbox -> tasks
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import INBOX_TOPIC, KAFKA_BOOTSTRAP, TASKS_TOPIC

from agents_kafka.common import ask_model, dumps

SYSTEM = (
    "You are a Planner for a restaurant-inspection knowledge system. "
    "Given a user question, output a short numbered plan (3-5 steps) "
    "for answering it. Do not answer the question itself. Max 80 words."
)


async def main():
    consumer = AIOKafkaConsumer(
        INBOX_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="s1421-planner-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_interval_ms=900_000,
        max_poll_records=1,
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await consumer.start()
    await producer.start()
    print(f"[PLANNER] listening on {INBOX_TOPIC}")
    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            correlation_id = payload.get("correlation_id")
            question = payload.get("question", "")
            if not correlation_id or not question:
                print("[PLANNER] skip invalid inbox message")
                await consumer.commit()
                continue
            print(f"[PLANNER] got correlation_id={correlation_id} question={question!r}")
            plan = ask_model(SYSTEM, question)
            out = {
                "correlation_id": correlation_id,
                "question": question,
                "plan": plan,
                "entity_key": payload.get("entity_key") or "general",
            }
            key = str(out["entity_key"]).encode()
            await producer.send_and_wait(TASKS_TOPIC, dumps(out), key=key)
            await consumer.commit()
            print(f"[PLANNER] sent plan to {TASKS_TOPIC}: {plan[:120]!r}")
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
