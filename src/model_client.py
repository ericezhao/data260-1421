"""Stable adapter for all Homework 1 model calls."""

from dataclasses import dataclass
from typing import Any, Sequence

from langchain_ollama import ChatOllama


@dataclass(frozen=True)
class ModelResponse:
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class OllamaModelClient:
    """Small adapter that hides Ollama/LangChain-specific response details."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        num_ctx: int = 4096,
        num_predict: int = 256,
        reasoning: bool = False,
        keep_alive: str = "30m",
        output_format: str | None = None,
    ) -> None:
        self._model = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            reasoning=reasoning,
            keep_alive=keep_alive,
            format=output_format,
        )

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        tools: Sequence[Any] | None = None,
    ) -> ModelResponse:
        """Complete a chat request through one stable interface."""
        runnable = self._model.bind_tools(list(tools)) if tools else self._model
        response = runnable.invoke(list(messages))

        usage = response.usage_metadata or {}
        metadata = response.response_metadata or {}
        input_tokens = int(
            usage.get("input_tokens")
            or metadata.get("prompt_eval_count")
            or 0
        )
        output_tokens = int(
            usage.get("output_tokens")
            or metadata.get("eval_count")
            or 0
        )
        total_tokens = int(
            usage.get("total_tokens")
            or input_tokens + output_tokens
        )

        content = response.content
        if isinstance(content, list):
            content = "".join(
                str(block.get("text", "")) if isinstance(block, dict) else str(block)
                for block in content
            )

        return ModelResponse(
            content=str(content).strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
