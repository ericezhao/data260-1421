# worker: read requests, write replies
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from kafka_rpc.config import KAFKA_BOOTSTRAP, REQUEST_TOPIC
from kafka_rpc.entity_store import process_operation


async def main():
    consumer = AIOKafkaConsumer(
        REQUEST_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="s1421-inspection-worker-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # commit after we finish (part 3)
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)

    await consumer.start()
    await producer.start()
    print("Consumer is ready and listening...")
    print(f"Topic={REQUEST_TOPIC} bootstrap={KAFKA_BOOTSTRAP}")

    try:
        async for msg in consumer:
            payload = json.loads(msg.value.decode())
            correlation_id = payload.get("correlation_id")
            reply_to = payload.get("reply_to")
            operation = payload.get("operation")
            data = payload.get("data") or {}

            print("\n[WORKER] Received message from REQUEST topic")
            print(f"[WORKER] Topic={msg.topic}, Partition={msg.partition}, Offset={msg.offset}")
            print(f"[WORKER] Full request message={json.dumps(payload, indent=2)}")
            print(f"[WORKER] correlation_id={correlation_id}")
            print(f"[WORKER] reply_to={reply_to}")

            result = process_operation(operation, data, correlation_id=correlation_id)
            response = {"correlation_id": correlation_id, **result}

            print("[WORKER] Sending message to RESPONSE topic")
            print(f"[WORKER] Response message={json.dumps(response, indent=2)}")

            meta = await producer.send_and_wait(reply_to, json.dumps(response).encode())
            print(
                f"[WORKER] Sent to topic={meta.topic}, "
                f"partition={meta.partition}, offset={meta.offset}"
            )
            await consumer.commit()
            print(f"[WORKER] Offset committed for partition={msg.partition}")
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
