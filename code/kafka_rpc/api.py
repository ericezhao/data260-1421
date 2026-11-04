# routes for kafka inspections (+ a direct path for comparison)
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from .entity_store import INSPECTIONS, process_operation, validate_create
from .kafka_rpc import KafkaRPC

rpc = KafkaRPC()
router = APIRouter(tags=["Kafka inspections"])


@asynccontextmanager
async def kafka_lifespan(_app: FastAPI):
    try:
        await rpc.start()
    except Exception as e:
        print(f"[KafkaRPC] start failed: {type(e).__name__}: {e}")
    yield
    try:
        await rpc.stop()
    except Exception:
        pass


@router.post("/api/kafka/inspections")
async def kafka_inspection_op(payload: dict):
    operation = payload.get("operation")
    data = payload.get("data") or {
        k: v for k, v in payload.items() if k not in {"operation", "correlation_id"}
    }
    if not operation:
        return {"success": False, "error": "operation is required"}
    return await rpc.make_request(operation, data, correlation_id=payload.get("correlation_id"))


@router.post("/api/inspections-direct")
async def direct_inspection_op(payload: dict):
    # same store, no kafka (for jmeter / quick checks)
    operation = payload.get("operation")
    data = payload.get("data") or {k: v for k, v in payload.items() if k != "operation"}
    if operation == "CREATE_INSPECTION":
        err = validate_create(data)
        if err:
            return {"success": False, "error": err}
    return process_operation(operation, data)


@router.get("/api/kafka/health")
async def kafka_health():
    return {
        "ok": True,
        "pending": list(rpc.pending.keys()),
        "direct_store_size": len(INSPECTIONS),
    }
