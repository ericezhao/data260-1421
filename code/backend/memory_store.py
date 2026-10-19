import csv
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model_client import OllamaModelClient

from embedder import cosine, embed_text
from file_memory import consolidation_due, load_file_memory, memory_text
from mongo_config import (
    COMPRESS_CHARS,
    COMPRESS_KEEP,
    EPISODE_TOP_K,
    LIFETIME_EVERY,
    SHORT_TERM_N,
    SUMMARIZE_EVERY_USER_MSGS,
)
from mongo_db import ensure_collections, episodes, messages, summaries
from mongo_utils import now_utc

RAW_DIR = ROOT / "reports" / "hw06" / "raw"
TURN_LOG = RAW_DIR / "chat_turns.csv"
TURN_COLUMNS = [
    "ts", "run_label", "phase", "user_id", "session_id", "prompt_tokens", "completion_tokens",
    "primer_tokens", "long_term_tokens", "short_term_tokens", "episodic_tokens", "latency_ms",
    "policy", "short_term_n",
]

PRIMER = (
    "You are a restaurant inspection assistant. "
    "Personal facts the user states, and the episodic facts and summaries below, "
    "are about this user and override the project description. "
    "Do not correct those personal facts. "
    "If none of the memory contains the answer, say you do not know. "
    "Answer in one or two plain sentences and do not start the reply with a dash. "
    "The bullet-only rule in AGENT.md applies only when the user asks for a code review."
)

_chat_model = None
_json_model = None


def chat_model() -> OllamaModelClient:
    global _chat_model
    if _chat_model is None:
        _chat_model = OllamaModelClient(
            model="qwen3:8b", temperature=0.0, num_predict=120, num_ctx=4096
        )
    return _chat_model


def json_model() -> OllamaModelClient:
    global _json_model
    if _json_model is None:
        _json_model = OllamaModelClient(
            model="qwen3:8b", temperature=0.0, num_predict=160, num_ctx=4096, output_format="json"
        )
    return _json_model


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_json_object(text: str) -> dict:
    raw = strip_think(text)
    if "```" in raw:
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json object")
    return json.loads(raw[start:end + 1])


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def save_message(user_id: str, session_id: str, role: str, content: str) -> None:
    messages().insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": now_utc(),
    })


def load_window(user_id: str, session_id: str, limit: int) -> list[dict]:
    docs = list(
        messages()
        .find({"user_id": user_id, "session_id": session_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    docs.reverse()
    return [{"role": doc["role"], "content": doc["content"]} for doc in docs]


def latest_summary(user_id: str, session_id: str | None, scope: str) -> str | None:
    query = {"user_id": user_id, "scope": scope}
    if scope == "session":
        query["session_id"] = session_id
    else:
        query["session_id"] = None
    doc = summaries().find_one(query, sort=[("created_at", -1)])
    if not doc:
        return None
    return doc.get("text")


def retrieve_episodes(user_id: str, query_text: str, top_k: int = EPISODE_TOP_K) -> list[dict]:
    query_vec = embed_text(query_text)
    ranked = []
    for doc in episodes().find({"user_id": user_id}):
        stored = doc.get("embedding") or []
        ranked.append({
            "fact": doc["fact"],
            "importance": doc["importance"],
            "similarity": round(cosine(query_vec, stored), 4),
        })
    ranked.sort(key=lambda item: (item["similarity"], item["importance"]), reverse=True)
    return ranked[:top_k]


def compress_history(history: list[dict], policy: str) -> list[dict]:
    if policy != "compress" or len(history) <= COMPRESS_KEEP:
        return history
    older = history[:-COMPRESS_KEEP]
    recent = history[-COMPRESS_KEEP:]
    bits = [f"{item['role']}: {item['content'][:COMPRESS_CHARS]}" for item in older]
    digest = "Earlier turns compressed: " + " | ".join(bits)
    return [
        {"role": "user", "content": digest},
        {"role": "assistant", "content": "Noted."},
        *recent,
    ]


def _section_tokens(sections: dict[str, str], prompt_tokens: int) -> dict[str, int]:
    lengths = {name: len(text) for name, text in sections.items()}
    total = sum(lengths.values())
    if prompt_tokens <= 0 or total <= 0:
        return {name: (max(1, length // 4) if length else 0) for name, length in lengths.items()}
    allocated = {name: int(round(prompt_tokens * length / total)) for name, length in lengths.items()}
    drift = prompt_tokens - sum(allocated.values())
    largest = max(allocated, key=allocated.get)
    allocated[largest] += drift
    return allocated


def _complete(model: OllamaModelClient, messages_in: list[dict]) -> str:
    return strip_think(model.complete(messages_in).content)


def extract_facts(message: str) -> list[dict]:
    facts = []
    if message.startswith("My "):
        facts.append({"fact": message.strip()[:200], "importance": 0.9})
    try:
        reply = _complete(json_model(), [
            {"role": "system", "content": "Extract durable facts. Return JSON only."},
            {"role": "user", "content": (
                "Message:\n" + message + "\n\n"
                'Return {"facts":[{"fact":"short text","importance":0.8}]} with at most 3 facts. '
                "importance is a number from 0 to 1. Use an empty list when nothing should be stored."
            )},
        ])
        payload = parse_json_object(reply)
        for item in payload.get("facts") or []:
            if len(facts) >= 3:
                break
            fact = str(item.get("fact", "")).strip()[:200]
            if not fact or any(existing["fact"] == fact for existing in facts):
                continue
            try:
                importance = float(item.get("importance", 0.5))
            except (TypeError, ValueError):
                importance = 0.5
            importance = min(1.0, max(0.0, importance))
            facts.append({"fact": fact, "importance": importance})
    except Exception:
        if not facts and len(message.split()) >= 6:
            facts.append({"fact": message.strip()[:200], "importance": 0.5})
    return facts[:3]


def store_episodes(user_id: str, session_id: str, facts: list[dict]) -> None:
    for item in facts:
        importance = float(item["importance"])
        episodes().insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "fact": item["fact"],
            "importance": importance,
            "embedding": embed_text(item["fact"]),
            "created_at": now_utc(),
        })


def _transcript(rows: list[dict]) -> str:
    return "\n".join(f"{row['role']}: {row['content']}" for row in rows)


def maybe_summarize(user_id: str, session_id: str) -> None:
    user_count = messages().count_documents({
        "user_id": user_id, "session_id": session_id, "role": "user",
    })
    if user_count == 0 or user_count % SUMMARIZE_EVERY_USER_MSGS != 0:
        return
    recent = load_window(user_id, session_id, 8)
    previous = latest_summary(user_id, session_id, "session") or "(none)"
    try:
        text = _complete(chat_model(), [
            {"role": "system", "content": "Summarize restaurant-inspection conversations."},
            {"role": "user", "content": (
                "Update the session summary in at most 8 bullet lines. "
                "Keep every name and number from the previous summary.\n\n"
                f"Previous summary:\n{previous}\n\nRecent messages:\n{_transcript(recent)}"
            )},
        ])
    except Exception:
        text = "\n".join(f"- {row['content'][:120]}" for row in recent if row["role"] == "user")
    if not text:
        return
    summaries().insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "scope": "session",
        "text": text[:2000],
        "created_at": now_utc(),
    })
    session_count = summaries().count_documents({"user_id": user_id, "scope": "session"})
    if session_count % LIFETIME_EVERY == 0:
        write_lifetime(user_id)


def write_lifetime(user_id: str) -> None:
    docs = list(
        summaries()
        .find({"user_id": user_id, "scope": "session"})
        .sort("created_at", -1)
        .limit(6)
    )
    docs.reverse()
    previous = latest_summary(user_id, None, "user") or "(none)"
    combined = "\n\n".join(doc["text"] for doc in docs)
    try:
        text = _complete(chat_model(), [
            {"role": "system", "content": "Condense session summaries into one lifetime summary."},
            {"role": "user", "content": (
                "Write at most 8 bullet lines. Keep names and numbers.\n\n"
                f"Previous lifetime summary:\n{previous}\n\nSession summaries:\n{combined}"
            )},
        ])
    except Exception:
        text = combined[:800]
    if not text:
        return
    summaries().insert_one({
        "user_id": user_id,
        "session_id": None,
        "scope": "user",
        "text": text[:2000],
        "created_at": now_utc(),
    })


def _log_turn(row: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not TURN_LOG.exists()
    with TURN_LOG.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TURN_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def run_chat(
    user_id: str,
    session_id: str | None,
    message: str,
    short_term_n: int | None = None,
    policy: str = "none",
    run_label: str = "live",
    phase: str = "live",
) -> dict:
    started = time.perf_counter()
    ensure_collections()
    session_id = session_id or uuid.uuid4().hex[:12]
    window_n = short_term_n or SHORT_TERM_N

    save_message(user_id, session_id, "user", message)
    loaded = load_window(user_id, session_id, window_n)
    history = loaded[:-1] if loaded and loaded[-1]["content"] == message else loaded
    history = compress_history(history, policy)
    session_summary = latest_summary(user_id, session_id, "session")
    lifetime_summary = latest_summary(user_id, None, "user")
    found = retrieve_episodes(user_id, message)

    long_parts = []
    if lifetime_summary:
        long_parts.append("Lifetime summary:\n" + lifetime_summary)
    if session_summary:
        long_parts.append("Session summary:\n" + session_summary)
    long_text = "\n\n".join(long_parts)
    episode_text = "\n".join(
        f"- {item['fact']} (importance {item['importance']})" for item in found
    )
    primer = "File memory:\n" + load_file_memory() + "\n\n" + PRIMER
    prompt = [{"role": "system", "content": primer}]
    if long_text:
        prompt.append({"role": "system", "content": long_text})
    if episode_text:
        prompt.append({"role": "system", "content": "Episodic facts:\n" + episode_text})
    prompt.extend(history)
    prompt.append({"role": "user", "content": message})

    response = chat_model().complete(prompt)
    reply = strip_think(response.content) or "I do not know."
    save_message(user_id, session_id, "assistant", reply)
    maybe_summarize(user_id, session_id)
    store_episodes(user_id, session_id, extract_facts(message))

    used = history + [{"role": "user", "content": message}]
    sections = {
        "primer": primer,
        "long_term": long_text,
        "short_term": _transcript(used),
        "episodic": episode_text,
        "current": message,
    }
    shares = _section_tokens(sections, response.input_tokens)
    latency_ms = int((time.perf_counter() - started) * 1000)
    _log_turn({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_label": run_label,
        "phase": phase,
        "user_id": user_id,
        "session_id": session_id,
        "prompt_tokens": response.input_tokens,
        "completion_tokens": response.output_tokens,
        "primer_tokens": shares["primer"],
        "long_term_tokens": shares["long_term"],
        "short_term_tokens": shares["short_term"],
        "episodic_tokens": shares["episodic"],
        "latency_ms": latency_ms,
        "policy": policy,
        "short_term_n": window_n,
    })
    return {
        "reply": reply,
        "user_id": user_id,
        "session_id": session_id,
        "memory_used": {
            "short_term_count": len(used),
            "short_term": used,
            "long_term": long_text or None,
            "episodes": found,
        },
        "usage": {
            "prompt_tokens": response.input_tokens,
            "completion_tokens": response.output_tokens,
            "primer_tokens": shares["primer"],
            "long_term_tokens": shares["long_term"],
            "short_term_tokens": shares["short_term"],
            "episodic_tokens": shares["episodic"],
            "latency_ms": latency_ms,
        },
        "consolidation_due": consolidation_due(memory_text()),
    }


def public_message(doc: dict) -> dict:
    return {
        "role": doc["role"],
        "content": doc["content"],
        "session_id": doc["session_id"],
        "created_at": _iso(doc["created_at"]),
    }


def public_summary(doc: dict) -> dict:
    return {
        "scope": doc["scope"],
        "session_id": doc.get("session_id"),
        "text": doc["text"],
        "created_at": _iso(doc["created_at"]),
    }


def public_episode(doc: dict) -> dict:
    embedding = doc.get("embedding") or []
    return {
        "fact": doc["fact"],
        "importance": doc["importance"],
        "session_id": doc["session_id"],
        "embedding_dims": len(embedding),
        "created_at": _iso(doc["created_at"]),
    }


def memory_view(user_id: str) -> dict:
    ensure_collections()
    rows = list(messages().find({"user_id": user_id}).sort("created_at", -1).limit(16))
    rows.reverse()
    session_doc = summaries().find_one(
        {"user_id": user_id, "scope": "session"}, sort=[("created_at", -1)]
    )
    lifetime_doc = summaries().find_one(
        {"user_id": user_id, "scope": "user"}, sort=[("created_at", -1)]
    )
    episode_docs = list(episodes().find({"user_id": user_id}).sort("created_at", -1).limit(20))
    return {
        "user_id": user_id,
        "messages": [public_message(doc) for doc in rows],
        "session_summary": public_summary(session_doc) if session_doc else None,
        "lifetime_summary": public_summary(lifetime_doc) if lifetime_doc else None,
        "episodes": [public_episode(doc) for doc in episode_docs],
    }


def aggregate_view(user_id: str) -> dict:
    ensure_collections()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily = [
        {"date": row["_id"], "count": row["count"]}
        for row in messages().aggregate(pipeline)
    ]
    recent = list(summaries().find({"user_id": user_id}).sort("created_at", -1).limit(5))
    return {
        "user_id": user_id,
        "daily_counts": daily,
        "recent_summaries": [public_summary(doc) for doc in recent],
    }
