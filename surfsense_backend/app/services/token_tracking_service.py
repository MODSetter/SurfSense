"""
Token usage tracking via LiteLLM custom callback.

Uses a ContextVar-scoped accumulator to group all LLM calls within a single
async request/turn. The accumulated data is emitted via SSE and persisted
when the frontend calls appendMessage.

Agent LLM calls are captured automatically via the async callback.
Title-generation usage is added explicitly from the LangChain response
metadata to avoid callback-timing issues.
"""

from __future__ import annotations

import dataclasses
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger(__name__)


@dataclass
class TokenCallRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class TurnTokenAccumulator:
    """Accumulates token usage across all LLM calls within a single user turn."""

    calls: list[TokenCallRecord] = field(default_factory=list)

    def add(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        self.calls.append(
            TokenCallRecord(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        )

    def per_message_summary(self) -> dict[str, dict[str, int]]:
        """Return token counts grouped by model name."""
        by_model: dict[str, dict[str, int]] = {}
        for c in self.calls:
            entry = by_model.setdefault(
                c.model,
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )
            entry["prompt_tokens"] += c.prompt_tokens
            entry["completion_tokens"] += c.completion_tokens
            entry["total_tokens"] += c.total_tokens
        return by_model

    @property
    def grand_total(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    def serialized_calls(self) -> list[dict[str, Any]]:
        return [dataclasses.asdict(c) for c in self.calls]


_turn_accumulator: ContextVar[TurnTokenAccumulator | None] = ContextVar(
    "_turn_accumulator", default=None
)


def start_turn() -> TurnTokenAccumulator:
    """Create a fresh accumulator for the current async context and return it."""
    acc = TurnTokenAccumulator()
    _turn_accumulator.set(acc)
    logger.info("[TokenTracking] start_turn: new accumulator created (id=%s)", id(acc))
    return acc


def get_current_accumulator() -> TurnTokenAccumulator | None:
    return _turn_accumulator.get()


class TokenTrackingCallback(CustomLogger):
    """LiteLLM callback that captures token usage into the turn accumulator."""

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: Any,
        end_time: Any,
    ) -> None:
        acc = _turn_accumulator.get()
        if acc is None:
            logger.debug("[TokenTracking] async_log_success_event fired but no accumulator in context")
            return

        usage = getattr(response_obj, "usage", None)
        if not usage:
            logger.debug("[TokenTracking] async_log_success_event fired but response has no usage data")
            return

        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or 0

        model = kwargs.get("model", "unknown")

        acc.add(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        logger.info(
            "[TokenTracking] Captured: model=%s prompt=%d completion=%d total=%d (accumulator now has %d calls)",
            model, prompt_tokens, completion_tokens, total_tokens, len(acc.calls),
        )


token_tracker = TokenTrackingCallback()
