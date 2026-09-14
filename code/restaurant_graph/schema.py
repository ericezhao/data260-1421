from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator

_CODE_DIR = Path(__file__).resolve().parent.parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from agents_demo import extract_json_block


class PlannerOutput(BaseModel):
    tags: list[str] = Field(min_length=3, max_length=3)
    summary: str

    @field_validator("tags")
    @classmethod
    def tag_length(cls, tags: list[str]) -> list[str]:
        cleaned = []
        for tag in tags:
            text = str(tag).strip()
            if len(text) < 3 or len(text) > 30:
                raise ValueError("each tag must be 3-30 characters")
            cleaned.append(text)
        return cleaned

    @field_validator("summary")
    @classmethod
    def summary_word_limit(cls, summary: str) -> str:
        text = str(summary).strip()
        if not text:
            raise ValueError("summary is empty")
        if len(text.split()) > 25:
            raise ValueError("summary must be at most 25 words")
        return text


def parse_planner_json(text: str) -> Dict[str, Any]:
    try:
        obj = json.loads(extract_json_block(text))
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        return {}
    data = obj.get("data")
    if not isinstance(data, dict):
        data = obj
    return {
        "thought": obj.get("thought", ""),
        "message": obj.get("message", ""),
        "tags": data.get("tags"),
        "summary": data.get("summary"),
    }


def validate_planner_output(text: str) -> Tuple[Dict[str, Any] | None, str]:
    parsed = parse_planner_json(text)
    try:
        output = PlannerOutput.model_validate(
            {"tags": parsed.get("tags"), "summary": parsed.get("summary")}
        )
    except ValidationError as err:
        return None, err.errors()[0].get("msg") if err.errors() else str(err)

    proposal = {
        "thought": str(parsed.get("thought") or ""),
        "message": str(parsed.get("message") or ""),
        "data": {
            "tags": output.tags,
            "summary": output.summary,
            "issues": [],
        },
    }
    return proposal, ""
