# put a question on inbox and wait for final
import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from kafka_rpc.config import FINAL_TOPIC, INBOX_TOPIC, KAFKA_BOOTSTRAP

from agents_kafka.common import dumps


async def main(question, entity_key):
    correlation_id = str(uuid.uuid4())
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    consumer = AIOKafkaConsumer(
        FINAL_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"s1421-sender-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await producer.start()
    await consumer.start()
    try:
        msg = {
            "correlation_id": correlation_id,
            "question": question,
            "entity_key": entity_key,
        }
        print(f"[SEND] correlation_id={correlation_id}")
        print(f"[SEND] -> {INBOX_TOPIC}: {json.dumps(msg)}")
        await producer.send_and_wait(INBOX_TOPIC, dumps(msg))
        print(f"[SEND] waiting on {FINAL_TOPIC} ...")
        async for raw in consumer:
            data = json.loads(raw.value.decode())
            if data.get("correlation_id") != correlation_id:
                continue
            print("[SEND] final message:")
            print(json.dumps(data, indent=2))
            return
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "question",
        nargs="?",
        default="Which cuisine tends to score lowest in local restaurant inspections?",
    )
    parser.add_argument("--entity-key", default="cuisine-general")
    args = parser.parse_args()
    asyncio.run(main(args.question, args.entity_key))
