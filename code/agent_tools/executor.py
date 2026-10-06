"""Single entry point the agent uses to call the three domain tools."""

import json
import re
from functools import lru_cache
from typing import Any

from domain_tools import TOOL_INPUTS, MySQLRepository, Repository, fail, run_tool

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")


@lru_cache(maxsize=1)
def _default_repo() -> MySQLRepository:
    return MySQLRepository()


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def safety_violation(inputs: dict) -> str | None:
    """Owner contact details are private: refuse any tool input that contains an email or phone number."""
    for text in _strings(inputs):
        if EMAIL_RE.search(text):
            return "blocked by safety rule: inputs must not contain an email address (owner contact data is private)"
        if PHONE_RE.search(text):
            return "blocked by safety rule: inputs must not contain a phone number (owner contact data is private)"
    return None


def execute_tool(name: str, inputs: Any, repo: Repository | None = None) -> str:
    """Run one domain tool and return the {ok, data, error} envelope as a JSON string. Never raises."""
    try:
        if isinstance(inputs, str):
            try:
                inputs = json.loads(inputs) if inputs.strip() else {}
            except ValueError:
                return json.dumps(fail("invalid input: inputs is not valid JSON"))
        if name not in TOOL_INPUTS:
            return json.dumps(fail(f"unknown tool '{name}'. Available: {', '.join(TOOL_INPUTS)}"))
        if not isinstance(inputs, dict):
            return json.dumps(fail("invalid input: inputs must be a JSON object"))
        blocked = safety_violation(inputs)
        if blocked:
            return json.dumps(fail(blocked))
        return json.dumps(run_tool(name, inputs, repo or _default_repo()), default=str)
    except Exception as exc:
        return json.dumps(fail(f"internal error: {type(exc).__name__}: {exc}"))
