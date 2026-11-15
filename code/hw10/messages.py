# save plan/draft/final keyed by correlation_id
import json
from pathlib import Path

from hw10.config import MESSAGES_DIR


class MessageStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else MESSAGES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, correlation_id):
        return self.root / f"{correlation_id}.json"

    def save(self, correlation_id, record):
        path = self.path_for(correlation_id)
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def load(self, correlation_id):
        path = self.path_for(correlation_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_stages(self, correlation_id):
        rec = self.load(correlation_id)
        if not rec:
            return None
        return {
            "correlation_id": correlation_id,
            "question": rec.get("question"),
            "plan": rec.get("plan"),
            "draft": rec.get("draft"),
            "final": rec.get("final") or rec.get("answer"),
            "cache_hit": bool(rec.get("cache_hit")),
            "metadata": rec.get("metadata") or {},
        }
