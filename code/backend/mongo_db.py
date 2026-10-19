from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.collection import Collection

from mongo_config import settings

_client = None
_ready = False

CUISINES = ["American", "Chinese", "Italian", "Japanese", "Mexican", "Indian", "Thai", "Other"]
STATUSES = ["open", "closed", "follow_up"]
SEVERITIES = ["critical", "major", "minor"]

INSPECTION_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["restaurantName", "status", "cuisine", "inspectedAt", "createdAt", "updatedAt"],
        "properties": {
            "restaurantName": {"bsonType": "string", "minLength": 1, "maxLength": 100},
            "notes": {"bsonType": "string", "maxLength": 2000},
            "status": {"enum": STATUSES},
            "cuisine": {"enum": CUISINES},
            "inspectedAt": {"bsonType": "date"},
            "score": {"bsonType": ["int", "long"], "minimum": 0, "maximum": 100},
            "owner": {
                "bsonType": "object",
                "required": ["name"],
                "properties": {
                    "name": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                    "phone": {"bsonType": "string", "maxLength": 20},
                },
            },
            "violations": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["description", "severity"],
                    "properties": {
                        "description": {"bsonType": "string", "minLength": 1, "maxLength": 300},
                        "severity": {"enum": SEVERITIES},
                    },
                },
            },
            "createdAt": {"bsonType": "date"},
            "updatedAt": {"bsonType": "date"},
        },
    }
}

MESSAGE_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "role", "content", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string", "minLength": 1, "maxLength": 80},
            "session_id": {"bsonType": "string", "minLength": 1, "maxLength": 80},
            "role": {"enum": ["user", "assistant"]},
            "content": {"bsonType": "string", "minLength": 1},
            "created_at": {"bsonType": "date"},
        },
    }
}

SUMMARY_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "scope", "text", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string", "minLength": 1, "maxLength": 80},
            "session_id": {"bsonType": ["string", "null"]},
            "scope": {"enum": ["session", "user"]},
            "text": {"bsonType": "string", "minLength": 1},
            "created_at": {"bsonType": "date"},
        },
    }
}

EPISODE_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "fact", "importance", "embedding", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string", "minLength": 1, "maxLength": 80},
            "session_id": {"bsonType": "string", "minLength": 1, "maxLength": 80},
            "fact": {"bsonType": "string", "minLength": 1, "maxLength": 300},
            "importance": {"bsonType": "double", "minimum": 0, "maximum": 1},
            "embedding": {"bsonType": "array", "items": {"bsonType": "double"}, "minItems": 8},
            "created_at": {"bsonType": "date"},
        },
    }
}


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
    return _client


def get_db():
    return get_client()[settings.MONGODB_DB]


def _ensure_collection(db, name: str, validator: dict) -> Collection:
    if name not in db.list_collection_names():
        return db.create_collection(name, validator={"$jsonSchema": validator["$jsonSchema"]})
    db.command("collMod", name, validator=validator, validationLevel="strict")
    return db[name]


def inspections() -> Collection:
    return get_db()["inspections"]


def messages() -> Collection:
    return get_db()["messages"]


def summaries() -> Collection:
    return get_db()["summaries"]


def episodes() -> Collection:
    return get_db()["episodes"]


def ensure_collections() -> None:
    global _ready
    if _ready:
        return
    db = get_db()
    _ensure_collection(db, "inspections", INSPECTION_VALIDATOR)
    _ensure_collection(db, "messages", MESSAGE_VALIDATOR)
    _ensure_collection(db, "summaries", SUMMARY_VALIDATOR)
    _ensure_collection(db, "episodes", EPISODE_VALIDATOR)
    messages().create_index([("user_id", 1), ("session_id", 1), ("created_at", 1)])
    summaries().create_index([("user_id", 1), ("scope", 1), ("created_at", -1)])
    episodes().create_index([("user_id", 1), ("created_at", -1)])
    seed_if_empty()
    _ready = True


def seed_if_empty() -> None:
    col = inspections()
    if col.count_documents({}) > 0:
        return
    now = datetime.now(timezone.utc)
    samples = [
        {
            "restaurantName": "Torihide Yakitori",
            "notes": "Counter seating. No violations on the last visit.",
            "status": "closed",
            "cuisine": "Japanese",
            "inspectedAt": datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc),
            "score": 100,
            "owner": {"name": "Maria Lopez", "phone": "408-555-0101"},
            "violations": [],
        },
        {
            "restaurantName": "Mission Steakhouse",
            "notes": "Walk-in cooler was above temperature.",
            "status": "follow_up",
            "cuisine": "American",
            "inspectedAt": datetime(2026, 10, 8, 15, 30, tzinfo=timezone.utc),
            "score": 92,
            "owner": {"name": "Daniel Brooks", "phone": "408-555-0194"},
            "violations": [{"description": "Cold food held too warm", "severity": "major"}],
        },
        {
            "restaurantName": "Red Sushi",
            "status": "open",
            "cuisine": "Japanese",
            "inspectedAt": datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc),
            "score": 98,
            "owner": {"name": "Kenji Sato", "phone": "408-555-0177"},
            "violations": [{"description": "Rice paddle stored on a towel", "severity": "minor"}],
        },
    ]
    for doc in samples:
        doc["createdAt"] = now
        doc["updatedAt"] = now
        col.insert_one(doc)
