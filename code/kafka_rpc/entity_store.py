# in-memory store for the kafka worker (not mysql)
import uuid

INSPECTIONS = {}
# same correlation_id should not create twice
PROCESSED = {}


def validate_create(data):
    if not isinstance(data, dict):
        return "data must be an object"
    if not data.get("restaurant_name") or not str(data.get("restaurant_name")).strip():
        return "restaurant_name is required"
    if not data.get("cuisine") or not str(data.get("cuisine")).strip():
        return "cuisine is required"
    if "score" not in data:
        return "score is required"
    score = data["score"]
    if not isinstance(score, int) or score < 0 or score > 100:
        return "score must be an integer between 0 and 100"
    return None


def process_operation(operation, data, correlation_id=None):
    if correlation_id and correlation_id in PROCESSED:
        out = dict(PROCESSED[correlation_id])
        out["idempotent_replay"] = True
        return out

    data = data or {}

    if operation == "CREATE_INSPECTION":
        err = validate_create(data)
        if err:
            return {"success": False, "error": err}
        inspection_id = str(uuid.uuid4())
        INSPECTIONS[inspection_id] = {
            "inspection_id": inspection_id,
            "restaurant_name": str(data["restaurant_name"]).strip(),
            "cuisine": str(data["cuisine"]).strip(),
            "score": int(data["score"]),
        }
        result = {
            "success": True,
            "inspection_id": inspection_id,
            "message": "Inspection created",
        }
        if correlation_id:
            PROCESSED[correlation_id] = dict(result)
        return result

    if operation == "GET_INSPECTION":
        inspection_id = data.get("inspection_id") or data.get("entity_id")
        if not inspection_id or inspection_id not in INSPECTIONS:
            return {"success": False, "error": "Inspection not found"}
        result = {"success": True, "entity": INSPECTIONS[inspection_id]}
        if correlation_id:
            PROCESSED[correlation_id] = dict(result)
        return result

    return {"success": False, "error": "Unknown operation"}
