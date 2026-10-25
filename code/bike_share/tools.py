"""csv_sql, policy_retriever, and calculator for the bike-share advisor."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import duckdb

SAFE_SQL = re.compile(r"^\s*select\b", re.I)
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|copy|pragma|create|replace|grant|revoke)\b",
    re.I,
)
CALC_RE = re.compile(r"^[0-9+\-*/().\s]+$")

CSV_SQL_SCHEMA = {
    "name": "csv_sql",
    "description": "Run a read-only SELECT over the uploaded trips CSV.",
    "parameters": {
        "type": "object",
        "properties": {"sql": {"type": "string"}},
        "required": ["sql"],
    },
}
POLICY_SCHEMA = {
    "name": "policy_retriever",
    "description": "Fetch a pricing page and return short quotable snippets.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "query": {"type": "string"},
            "k": {"type": "integer"},
        },
        "required": ["url", "query"],
    },
}
CALC_SCHEMA = {
    "name": "calculator",
    "description": "Evaluate a safe arithmetic expression.",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string"},
            "units": {"type": "string"},
        },
        "required": ["expression"],
    },
}

TOOL_SCHEMAS = [CSV_SQL_SCHEMA, POLICY_SCHEMA, CALC_SCHEMA]


def envelope(
    success: bool,
    data: Any = None,
    error: str | None = None,
    source: str | None = None,
) -> dict:
    return {
        "success": success,
        "data": data,
        "error": error,
        "source": source,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


class TripStore:
    def __init__(self, csv_path: Path | None = None):
        self.csv_path = csv_path
        self.con = duckdb.connect(database=":memory:")
        if csv_path is not None:
            self.load(csv_path)

    def load(self, csv_path: Path) -> None:
        self.csv_path = Path(csv_path)
        self.con.execute("DROP TABLE IF EXISTS trips")
        self.con.execute(
            "CREATE TABLE trips AS SELECT * FROM read_csv_auto(?, HEADER=TRUE)",
            [str(self.csv_path)],
        )

    def csv_sql(self, sql: str) -> dict:
        text = (sql or "").strip()
        if not text:
            return envelope(False, error="sql is required", source="uploaded.csv")
        # Enforce a single read-only SELECT contract regardless of model text.
        if ";" in text.rstrip(";"):
            return envelope(
                False,
                error="only a single SELECT statement is allowed",
                source="uploaded.csv",
            )
        if not SAFE_SQL.search(text) or FORBIDDEN_SQL.search(text):
            return envelope(
                False,
                error="csv_sql only allows read-only SELECT queries",
                source="uploaded.csv",
            )
        if self.csv_path is None:
            return envelope(False, error="no CSV uploaded", source="uploaded.csv")
        try:
            relation = self.con.execute(text)
            columns = [col[0] for col in relation.description]
            rows = [dict(zip(columns, row)) for row in relation.fetchall()]
            return envelope(
                True,
                data={"rows": rows, "row_count": len(rows), "source": "uploaded.csv"},
                source="uploaded.csv",
            )
        except Exception as exc:
            return envelope(
                False,
                error=f"{type(exc).__name__}: {exc}",
                source="uploaded.csv",
            )


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&\w+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_policy_text(url: str, fixture_text: str | None = None) -> dict:
    if fixture_text is not None:
        body = fixture_text
        source = "local-fixture"
    else:
        request = Request(url, headers={"User-Agent": "data260-hw7/1.0"})
        with urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
        source = url
    plain = _strip_html(body)
    digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return {
        "text": plain,
        "raw_html": body,
        "source": source,
        "sha256": digest,
        "accessed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": url,
    }


def policy_retriever(
    url: str,
    query: str,
    k: int = 4,
    fixture_text: str | None = None,
    cached: dict | None = None,
) -> dict:
    try:
        page = cached or fetch_policy_text(url, fixture_text=fixture_text)
        text = page["text"]
        # Label retrieved text as untrusted for the agent prompt builder.
        terms = [
            tok.lower() for tok in re.findall(r"[a-z0-9+$/.-]+", query.lower()) if len(tok) > 2
        ]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        scored = []
        for sentence in sentences:
            lower = sentence.lower()
            score = sum(1 for term in terms if term in lower)
            if score:
                scored.append((score, sentence.strip()))
        scored.sort(key=lambda item: (-item[0], -len(item[1])))
        if not scored:
            scored = [(1, sentence.strip()) for sentence in sentences[:k] if sentence.strip()]
        passages = [
            {
                "text": sentence[:400],
                "source": page["url"],
                "score": float(score),
                "untrusted": True,
            }
            for score, sentence in scored[: max(1, k)]
        ]
        return envelope(
            True,
            data={
                "passages": passages,
                "sha256": page["sha256"],
                "accessed_at": page["accessed_at"],
            },
            source=page["source"],
        )
    except Exception as exc:
        return envelope(False, error=f"{type(exc).__name__}: {exc}", source=url)


def calculator(expression: str, units: str | None = None) -> dict:
    expr = (expression or "").strip()
    if not expr or not CALC_RE.match(expr):
        return envelope(False, error="expression must match ^[0-9+\\-*/().\\s]+$")
    try:
        value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 - whitelisted chars only
        if not isinstance(value, (int, float)):
            return envelope(False, error="expression did not evaluate to a number")
        data = {"value": float(value)}
        if units:
            data["units"] = units
        return envelope(True, data=data, source="calculator")
    except Exception as exc:
        return envelope(False, error=f"{type(exc).__name__}: {exc}", source="calculator")


def run_tool(name: str, inputs: dict, store: TripStore, policy_cache: dict | None = None) -> dict:
    if name == "csv_sql":
        return store.csv_sql(str(inputs.get("sql", "")))
    if name == "policy_retriever":
        return policy_retriever(
            url=str(inputs.get("url", "")),
            query=str(inputs.get("query", "")),
            k=int(inputs.get("k") or 4),
            fixture_text=(policy_cache or {}).get("fixture_text"),
            cached=(policy_cache or {}).get("page"),
        )
    if name == "calculator":
        return calculator(str(inputs.get("expression", "")), inputs.get("units"))
    return envelope(False, error=f"unknown tool {name}")
