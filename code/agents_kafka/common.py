# shared helpers for the 3 agents
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code")]

from kafka_rpc.config import OLLAMA_MODEL


def dumps(obj):
    return json.dumps(obj).encode()


def ask_model(system, user, num_predict=220):
    # HW8_MOCK_LLM=1 = skip ollama (faster for part3 timing runs)
    if os.getenv("HW8_MOCK_LLM") == "1":
        if "Planner" in system or "numbered plan" in system:
            return (
                "1. Restate the inspection question.\n"
                "2. Note score meaning (0-100, higher is better).\n"
                "3. Give a short cuisine-aware answer."
            )
        if "Reviewer" in system or "Score the draft" in system:
            return (
                '{"status":"approved","score":8,'
                '"answer":"Inspection scores (0-100) summarize food-safety findings; '
                "higher is better. Sushi restaurants watch scores because raw fish "
                'handling is high risk and public grades affect trust."}'
            )
        return (
            "Inspection scores run from 0 to 100 (higher is better). "
            "For sushi places the score matters because raw fish handling is risky."
        )

    from src.model_client import OllamaModelClient

    model = os.getenv("HW8_OLLAMA_MODEL", OLLAMA_MODEL)
    client = OllamaModelClient(
        model=model,
        num_predict=num_predict,
        temperature=0.2,
        reasoning=False,
    )
    resp = client.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    text = resp.content
    if "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    return text.strip()
