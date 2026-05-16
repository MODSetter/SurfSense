"""Bare-LLM arm: chat completion with prompt-only input, no retrieval.

Pairs with ``SurfSenseArm`` for any benchmark that wants to measure
"how much does the model already know without RAG?". For factuality /
multi-hop benchmarks (FRAMES, MuSiQue, …) this produces the published
"naive prompting" baseline — e.g. FRAMES's 40.8% on Gemini-Pro-1.5.

Symmetric with ``NativePdfArm`` in shape, but the request carries no
``pdf_paths``: the prompt itself is the only input the model gets.
"""

from __future__ import annotations

import logging

from ..providers.openrouter_chat import OpenRouterChatProvider
from .base import Arm, ArmRequest, ArmResult

logger = logging.getLogger(__name__)


class BareLlmArm(Arm):
    """``Arm`` implementation backed by ``OpenRouterChatProvider``.

    ``name`` defaults to ``"bare_llm"`` but is overridable per-instance.
    Suites that want two distinct OpenRouter chat arms (e.g. CRAG's
    ``bare_llm`` vs ``long_context`` — both backed by chat-completions
    but exercising different prompt strategies) instantiate twice with
    different names so the metrics aggregator can keep them separate.
    """

    name: str = "bare_llm"

    def __init__(
        self,
        *,
        provider: OpenRouterChatProvider,
        max_output_tokens: int | None = 1024,
        system_prompt: str | None = None,
        name: str | None = None,
    ) -> None:
        self._provider = provider
        self._max_output = max_output_tokens
        self._system_prompt = system_prompt
        if name:
            self.name = name

    @classmethod
    def from_env(
        cls,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        max_output_tokens: int | None = 1024,
        system_prompt: str | None = None,
        name: str | None = None,
    ) -> BareLlmArm:
        provider = OpenRouterChatProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        return cls(
            provider=provider,
            max_output_tokens=max_output_tokens,
            system_prompt=system_prompt,
            name=name,
        )

    async def answer(self, request: ArmRequest) -> ArmResult:
        try:
            response = await self._provider.complete(
                prompt=request.prompt,
                system_prompt=self._system_prompt,
                max_tokens=self._max_output,
            )
        except Exception as exc:  # noqa: BLE001
            return ArmResult(
                arm=self.name,
                question_id=request.question_id,
                raw_text="",
                error=f"{type(exc).__name__}: {exc}",
            )
        return ArmResult(
            arm=self.name,
            question_id=request.question_id,
            raw_text=response.text,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_micros=response.cost_micros,
            latency_ms=response.latency_ms,
            extra={
                "model": self._provider.model,
                "finish_reason": response.finish_reason,
            },
        )


__all__ = ["BareLlmArm"]
