"""Three read-only tools over the s1421_rel restaurant-inspection data.

Every tool returns the same envelope: {"ok": bool, "data": ..., "error": str | None}.
The storage layer is injected (`repo`), so tests can pass a fake repository and run offline.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retry import RetryExhausted, RetryPolicy, Trace, TransientError, call_with_retry  # noqa: E402

log = logging.getLogger("domain_tools")

DEFAULT_POLICY = RetryPolicy(max_attempts=3, timeout_s=2.0, base_delay_s=0.1, max_delay_s=1.0)


# ----- input contracts -----
class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=100, description="Part of a restaurant name")
    cuisine: str | None = Field(default=None, max_length=50, description="Optional exact cuisine filter")
    limit: int = Field(default=10, ge=1, le=25)


class DetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inspection_code: str = Field(pattern=r"^INS-\d{5}$", description="Unique code such as INS-00042")


class SummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_by: Literal["cuisine", "owner"]
    top: int = Field(default=5, ge=1, le=20, description="Number of lowest-scoring groups to return")


TOOL_INPUTS: dict[str, type[BaseModel]] = {
    "search_inspections": SearchInput,
    "get_inspection": DetailInput,
    "score_summary": SummaryInput,
}


# ----- storage -----
class Repository(Protocol):
    def search(self, query: str, cuisine: str | None, limit: int) -> list[dict]: ...
    def get_by_code(self, code: str) -> dict | None: ...
    def score_summary(self, group_by: str, top: int) -> list[dict]: ...


class MySQLRepository:
    """Reads from MySQL through the backend's SQLAlchemy models."""

    def __init__(self):
        backend = Path(__file__).resolve().parents[1] / "backend"
        sys.path.insert(0, str(backend))
        import models
        from database import db_session_basede26
        from sqlalchemy import func
        from sqlalchemy.exc import OperationalError

        self.models = models
        self.Session = db_session_basede26
        self.func = func
        self.OperationalError = OperationalError

    def _run(self, work):
        db = self.Session()
        try:
            return work(db)
        except self.OperationalError as exc:
            raise TransientError(f"database error: {exc.orig}") from exc
        finally:
            db.close()

    def search(self, query, cuisine, limit):
        Inspection = self.models.Inspection

        def work(db):
            q = db.query(Inspection).filter(Inspection.restaurant_name.like(f"%{query}%"))
            if cuisine:
                q = q.filter(Inspection.cuisine == cuisine)
            return [_summary_row(r) for r in q.order_by(Inspection.id).limit(limit)]

        return self._run(work)

    def get_by_code(self, code):
        m = self.models

        def work(db):
            row = db.query(m.Inspection).filter(m.Inspection.inspection_code == code).first()
            if row is None:
                return None
            return {
                **_summary_row(row),
                "owner": {"id": row.owner.id, "name": row.owner.name},
                "violations": [
                    {"description": v.description, "severity": v.severity} for v in row.violations
                ],
                "createdAt": row.created_at.isoformat(),
            }

        return self._run(work)

    def score_summary(self, group_by, top):
        m, func = self.models, self.func
        label = m.Inspection.cuisine if group_by == "cuisine" else m.Owner.name

        def work(db):
            q = db.query(
                label.label("group"),
                func.count(m.Inspection.id),
                func.avg(m.Inspection.score),
                func.min(m.Inspection.score),
            )
            if group_by == "owner":
                q = q.join(m.Owner, m.Inspection.owner_id == m.Owner.id).group_by(m.Owner.id, m.Owner.name)
            else:
                q = q.group_by(m.Inspection.cuisine)
            rows = q.order_by(func.avg(m.Inspection.score).asc()).limit(top).all()
            return [
                {"group": g, "inspections": n, "avgScore": round(float(avg), 2), "minScore": low}
                for g, n, avg, low in rows
            ]

        return self._run(work)


def _summary_row(row) -> dict:
    return {
        "inspectionCode": row.inspection_code,
        "restaurantName": row.restaurant_name,
        "cuisine": row.cuisine,
        "score": row.score,
        "ownerId": row.owner_id,
    }


# ----- envelope -----
def ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None}


def fail(error: str) -> dict:
    return {"ok": False, "data": None, "error": error}


def _validation_message(exc: ValidationError) -> str:
    parts = [f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors()]
    return "invalid input: " + "; ".join(parts)


# ----- tools -----
def run_tool(
    name: str,
    inputs: dict,
    repo: Repository,
    policy: RetryPolicy = DEFAULT_POLICY,
    trace: Trace | None = None,
) -> dict:
    """Validate inputs, call storage with timeout + retry, and always return an envelope."""
    model = TOOL_INPUTS.get(name)
    if model is None:
        return fail(f"unknown tool '{name}'. Available: {', '.join(TOOL_INPUTS)}")
    if not isinstance(inputs, dict):
        return fail("invalid input: inputs must be a JSON object")
    try:
        args = model.model_validate(inputs)
    except ValidationError as exc:
        return fail(_validation_message(exc))

    if name == "search_inspections":
        call = lambda: repo.search(args.query, args.cuisine, args.limit)  # noqa: E731
    elif name == "get_inspection":
        call = lambda: repo.get_by_code(args.inspection_code)  # noqa: E731
    else:
        call = lambda: repo.score_summary(args.group_by, args.top)  # noqa: E731

    try:
        result = call_with_retry(call, policy, trace)
    except RetryExhausted as exc:
        log.error("%s failed: %s", name, exc)
        return fail(f"storage unavailable after {exc.attempts} attempts: {exc.last_error}")
    except Exception as exc:  # never let a storage bug crash the caller
        log.exception("%s crashed", name)
        return fail(f"internal error: {type(exc).__name__}")

    if name == "get_inspection" and result is None:
        return fail(f"inspection {args.inspection_code} not found")
    if name == "search_inspections":
        return ok({"count": len(result), "results": result})
    if name == "score_summary":
        return ok({"groupBy": args.group_by, "groups": result})
    return ok(result)
