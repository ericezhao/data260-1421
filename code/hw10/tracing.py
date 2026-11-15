# JSON spans; reuse HW8 correlation_id as trace_id
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from hw10.config import SPANS_DIR


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class SpanStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else SPANS_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, trace_id):
        return self.root / f"{trace_id}.jsonl"

    def write(self, span):
        path = self.path_for(span["trace_id"])
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(span, ensure_ascii=False) + "\n")
        return span

    def load(self, trace_id):
        path = self.path_for(trace_id)
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def list_trace_ids(self):
        return sorted(p.stem for p in self.root.glob("*.jsonl"))


@contextmanager
def span(store, trace_id, stage, extra=None):
    start = time.perf_counter()
    start_iso = _now_iso()
    status = "ok"
    error = None
    payload = dict(extra or {})
    try:
        yield payload
    except Exception as e:
        status = "error"
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        end = time.perf_counter()
        store.write(
            {
                "trace_id": trace_id,
                "stage": stage,
                "start": start_iso,
                "end": _now_iso(),
                "duration_ms": round((end - start) * 1000, 3),
                "status": status,
                "error": error,
                **payload,
            }
        )
