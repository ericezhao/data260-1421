# fastapi side: send request, wait for matching correlation_id
import asyncio
import json
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import KAFKA_BOOTSTRAP, REQUEST_TOPIC, RESPONSE_TOPIC, TIMEOUT_SECONDS


class KafkaRPC:
    def __init__(self):
        self.producer = None
        self.consumer = None
        self.pending = {}
        self.consumer_task = None

    async def start(self):
        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        self.consumer = AIOKafkaConsumer(
            RESPONSE_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="s1421-fastapi-response-group",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self.producer.start()
        await self.consumer.start()
        self.consumer_task = asyncio.create_task(self.consume_responses())
        print("FastAPI KafkaRPC started")
        print(f"Listening for Kafka responses on topic: {RESPONSE_TOPIC}")

    async def stop(self):
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        print("FastAPI KafkaRPC stopped")

    async def consume_responses(self):
        async for msg in self.consumer:
            data = json.loads(msg.value.decode())
            correlation_id = data.get("correlation_id")
            print("\n[FASTAPI] Received message from RESPONSE topic")
            print(f"[FASTAPI] Topic={msg.topic}, Partition={msg.partition}, Offset={msg.offset}")
            print(f"[FASTAPI] Message value={json.dumps(data, indent=2)}")
            if correlation_id in self.pending:
                fut = self.pending.pop(correlation_id)
                print(f"[FASTAPI] Matched correlation_id: {correlation_id}")
                if not fut.done():
                    fut.set_result(data)
            else:
                print(f"[FASTAPI] No pending request for correlation_id: {correlation_id}")

    async def make_request(self, operation, data, correlation_id=None):
        if self.producer is None:
            return {"success": False, "error": "KafkaRPC is not started"}
        correlation_id = correlation_id or str(uuid.uuid4())
        message = {
            "correlation_id": correlation_id,
            "reply_to": RESPONSE_TOPIC,
            "operation": operation,
            "data": data,
        }
        fut = asyncio.get_running_loop().create_future()
        self.pending[correlation_id] = fut

        print("\n[FASTAPI] Sending message to REQUEST topic")
        print(f"[FASTAPI] correlation_id={correlation_id}")
        print(f"[FASTAPI] reply_to={RESPONSE_TOPIC}")
        print(f"[FASTAPI] Message value={json.dumps(message, indent=2)}")

        meta = await self.producer.send_and_wait(REQUEST_TOPIC, json.dumps(message).encode())
        print(
            f"[FASTAPI] Sent to topic={meta.topic}, "
            f"partition={meta.partition}, offset={meta.offset}"
        )

        try:
            response = await asyncio.wait_for(fut, timeout=TIMEOUT_SECONDS)
            print(f"[FASTAPI] Final response matched for correlation_id={correlation_id}")
            print(f"[FASTAPI] Returning HTTP response to client: {response}")
            return response
        except TimeoutError:
            self.pending.pop(correlation_id, None)
            return {
                "correlation_id": correlation_id,
                "success": False,
                "error": f"Timeout for correlation_id {correlation_id}",
            }
