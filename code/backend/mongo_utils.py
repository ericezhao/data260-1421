from datetime import datetime, timezone

from bson import ObjectId


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_valid_object_id(value: str) -> bool:
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


def to_object_id(value: str) -> ObjectId:
    return ObjectId(value)


def serialize_inspection(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "restaurantName": doc.get("restaurantName"),
        "notes": doc.get("notes"),
        "status": doc.get("status"),
        "cuisine": doc.get("cuisine"),
        "inspectedAt": doc.get("inspectedAt"),
        "score": doc.get("score", 100),
        "owner": doc.get("owner"),
        "violations": doc.get("violations") or [],
        "createdAt": doc.get("createdAt"),
        "updatedAt": doc.get("updatedAt"),
    }
