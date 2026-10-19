from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pymongo.errors import PyMongoError

from file_memory import (
    append_learned,
    compact_memory,
    consolidation_due,
    help_text,
    load_file_memory,
    memory_text,
)
from memory_store import aggregate_view, memory_view, run_chat
from mongo_db import episodes, ensure_collections
from mongo_schemas import ChatIn

router = APIRouter(tags=["Memory"])
CHAT_PAGE = Path(__file__).resolve().parent / "chat.html"


def _dream(user_id: str) -> list[str]:
    ensure_collections()
    current = memory_text()
    added = []
    docs = episodes().find({"user_id": user_id}).sort("created_at", -1).limit(20)
    for doc in docs:
        fact = str(doc.get("fact", "")).strip()
        if not fact or fact in current or float(doc.get("importance", 0)) < 0.6:
            continue
        added.append(fact)
        if len(added) == 5:
            break
    append_learned(added)
    return added


@router.get("/chat-ui")
def chat_page():
    return FileResponse(CHAT_PAGE)


@router.post("/api/chat")
def chat(payload: ChatIn):
    command = payload.message.strip().split()[0].lower()
    if payload.message.strip().startswith("/"):
        if command == "/help":
            reply = help_text()
        elif command == "/memory":
            due = consolidation_due(memory_text())
            reply = load_file_memory() + f"\n\nconsolidation_due: {str(due).lower()}"
        elif command == "/compact":
            before, after = compact_memory()
            reply = f"MEMORY.md compacted: {before} content lines before, {after} content lines after."
        elif command == "/dream":
            try:
                added = _dream(payload.user_id)
            except PyMongoError:
                raise HTTPException(status_code=503, detail="MongoDB is not available.")
            reply = "Added to MEMORY.md: " + ("; ".join(added) if added else "nothing new.")
        else:
            raise HTTPException(status_code=400, detail="Unknown command. Try /help.")
        return {
            "reply": reply,
            "user_id": payload.user_id,
            "session_id": payload.session_id,
            "memory_used": None,
        }
    try:
        return run_chat(
            user_id=payload.user_id,
            session_id=payload.session_id,
            message=payload.message.strip(),
            short_term_n=payload.short_term_n,
            policy=payload.policy,
            run_label=payload.run_label,
            phase=payload.phase,
        )
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is not available.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Model error: {type(exc).__name__}: {exc}")


@router.get("/api/memory/{user_id}")
def read_memory(user_id: str):
    try:
        return memory_view(user_id)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is not available.")


@router.get("/api/aggregate/{user_id}")
def read_aggregate(user_id: str):
    try:
        return aggregate_view(user_id)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is not available.")
