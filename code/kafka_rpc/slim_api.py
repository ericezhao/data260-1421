# small fastapi app just for hw8 docker screenshots (port 8521)
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from kafka_rpc.api import kafka_lifespan, router
from kafka_rpc.config import PORT_BASE

app = FastAPI(title="s1421 kafka inspections", lifespan=kafka_lifespan)
app.include_router(router)


@app.get("/")
async def root():
    return {"ok": True, "port": PORT_BASE}


if __name__ == "__main__":
    print(f"Uvicorn running on http://127.0.0.1:{PORT_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
