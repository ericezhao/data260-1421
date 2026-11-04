# HW8 part1 demo: CREATE then GET over kafka
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from kafka_rpc.config import (
    KAFKA_BOOTSTRAP,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
    TIMEOUT_SECONDS,
)


async def wait_for_response(consumer, correlation_id):
    async for msg in consumer:
        data = json.loads(msg.value.decode())
        print("\n[CLIENT] Response received from RESPONSE topic")
        print(f"[CLIENT] Topic={msg.topic}, Partition={msg.partition}, Offset={msg.offset}")
        print(f"[CLIENT] Message value={json.dumps(data, indent=2)}")
        if data.get("correlation_id") == correlation_id:
            return data
    raise RuntimeError("no matching response")


async def send_and_receive(producer, consumer, operation, data):
    correlation_id = str(uuid.uuid4())
    message = {
        "correlation_id": correlation_id,
        "reply_to": RESPONSE_TOPIC,
        "operation": operation,
        "data": data,
    }
    print("\n[CLIENT] Sending message to REQUEST topic")
    print(f"[CLIENT] correlation_id={correlation_id}")
    print(f"[CLIENT] Message value={json.dumps(message, indent=2)}")
    meta = await producer.send_and_wait(REQUEST_TOPIC, json.dumps(message).encode())
    print(f"[CLIENT] Sent to topic={meta.topic}, partition={meta.partition}, offset={meta.offset}")
    response = await asyncio.wait_for(
        wait_for_response(consumer, correlation_id),
        timeout=TIMEOUT_SECONDS,
    )
    print(f"[CLIENT] correlation_id preserved={response.get('correlation_id')}")
    return response


async def main():
    print("Eric Zhao (SID4 1421) - HW8 homework_demo.py")
    print(f"REQUEST_TOPIC={REQUEST_TOPIC}")
    print(f"RESPONSE_TOPIC={RESPONSE_TOPIC}")

    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    consumer = AIOKafkaConsumer(
        RESPONSE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=f"s1421-demo-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    await producer.start()
    await consumer.start()
    try:
        create_resp = await send_and_receive(
            producer,
            consumer,
            "CREATE_INSPECTION",
            {
                "restaurant_name": "Blue Sushi Demo",
                "cuisine": "Japanese",
                "score": 95,
            },
        )
        assert create_resp.get("success") is True, create_resp
        inspection_id = create_resp["inspection_id"]
        print(f"\n[CLIENT] Created inspection_id={inspection_id}")

        get_resp = await send_and_receive(
            producer,
            consumer,
            "GET_INSPECTION",
            {"inspection_id": inspection_id},
        )
        assert get_resp.get("success") is True, get_resp
        print("\n[CLIENT] Retrieved entity:")
        print(json.dumps(get_resp.get("entity"), indent=2))
        print(
            "[CLIENT] CREATE -> GET sequence complete; "
            f"create_corr={create_resp.get('correlation_id')} "
            f"get_corr={get_resp.get('correlation_id')}"
        )
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
