"""
Token usage tracking via LiteLLM custom callback.

Uses a ContextVar-scoped accumulator to group all LLM calls within a single
async request/turn. The accumulated data is emitted via SSE and persisted
when the frontend calls appendMessage.

The module also provides ``record_token_usage``, a thin async helper that
creates a ``TokenUsage`` row for *any* usage type (chat, indexing, image
generation, podcasts, …).  Call sites should prefer this helper over
constructing ``TokenUsage`` manually so that logging and error handling
stay consistent.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import litellm
from litellm.integrations.custom_logger import CustomLogger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class TokenCallRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_micros: int = 0
    call_kind: str = "chat"


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
        cost_micros: int = 0,
        call_kind: str = "chat",
    ) -> None:
        self.calls.append(
            TokenCallRecord(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_micros=cost_micros,
                call_kind=call_kind,
            )
        )

    def per_message_summary(self) -> dict[str, dict[str, int]]:
        """Return token counts (and cost) grouped by model name."""
        by_model: dict[str, dict[str, int]] = {}
        for c in self.calls:
            entry = by_model.setdefault(
                c.model,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_micros": 0,
                },
            )
            entry["prompt_tokens"] += c.prompt_tokens
            entry["completion_tokens"] += c.completion_tokens
            entry["total_tokens"] += c.total_tokens
            entry["cost_micros"] += c.cost_micros
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

    @property
    def total_cost_micros(self) -> int:
        """Sum of per-call ``cost_micros`` across the entire turn.

        Used by ``stream_new_chat`` to debit a premium turn's actual
        provider cost (in micro-USD) from the user's premium credit
        balance. ``cost_micros`` per call is captured by
        ``TokenTrackingCallback.async_log_success_event`` from
        ``kwargs["response_cost"]`` (LiteLLM's auto-calculated cost),
        with multiple fallback paths so OpenRouter dynamic models and
        custom Azure deployments still bill correctly when our
        ``pricing_registration`` ran at startup.
        """
        return sum(c.cost_micros for c in self.calls)

    def serialized_calls(self) -> list[dict[str, Any]]:
        return [dataclasses.asdict(c) for c in self.calls]


_turn_accumulator: ContextVar[TurnTokenAccumulator | None] = ContextVar(
    "_turn_accumulator", default=None
)


def start_turn() -> TurnTokenAccumulator:
    """Create a fresh accumulator for the current async context and return it.

    NOTE: Used by ``stream_new_chat`` for the long-lived chat turn. For
    short-lived per-call billable wrappers (image generation REST endpoint,
    vision LLM during indexing) prefer :func:`scoped_turn`, which uses a
    ContextVar reset token to restore the *previous* accumulator on exit and
    avoids leaking call records across reservations (issue B).
    """
    acc = TurnTokenAccumulator()
    _turn_accumulator.set(acc)
    logger.info("[TokenTracking] start_turn: new accumulator created (id=%s)", id(acc))
    return acc


def get_current_accumulator() -> TurnTokenAccumulator | None:
    return _turn_accumulator.get()


@asynccontextmanager
async def scoped_turn() -> AsyncIterator[TurnTokenAccumulator]:
    """Async context manager that scopes a fresh ``TurnTokenAccumulator``
    for the duration of the ``async with`` block, then *resets* the
    ContextVar to its previous value on exit.

    This is the safe primitive for per-call billable operations
    (image generation, vision LLM extraction, podcasts) that may run
    inside an outer chat turn or be called sequentially from the same
    background worker. Using ``ContextVar.set`` without ``reset`` (as
    :func:`start_turn` does) would leak the inner accumulator into the
    outer scope, causing the outer chat turn to debit cost twice.

    Usage::

        async with scoped_turn() as acc:
            await llm.ainvoke(...)
            # acc.total_cost_micros captures cost from the LiteLLM callback
        # Outer accumulator (if any) is restored here.
    """
    acc = TurnTokenAccumulator()
    token = _turn_accumulator.set(acc)
    logger.debug(
        "[TokenTracking] scoped_turn: enter (acc id=%s, prev token=%s)",
        id(acc),
        token,
    )
    try:
        yield acc
    finally:
        _turn_accumulator.reset(token)
        logger.debug(
            "[TokenTracking] scoped_turn: exit (acc id=%s captured %d call(s), %d micros total)",
            id(acc),
            len(acc.calls),
            acc.total_cost_micros,
        )


def _extract_cost_usd(
    kwargs: dict[str, Any],
    response_obj: Any,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    is_image: bool = False,
) -> float:
    """Best-effort USD cost extraction for a single LLM/image call.

    Tries four sources in priority order and returns the first that
    yields a positive number; returns 0.0 if all four fail (the call
    will then debit nothing from the user's balance — fail-safe).

    Sources:
      1. ``kwargs["response_cost"]`` — LiteLLM's standard callback
         field, populated for ``Router.acompletion`` since PR #12500.
      2. ``response_obj._hidden_params["response_cost"]`` — same value
         exposed on the response itself.
      3. ``litellm.completion_cost(completion_response=response_obj)``
         — recompute from the response and LiteLLM's pricing table.
      4. ``litellm.cost_per_token(model, prompt_tokens, completion_tokens)``
         — manual fallback for OpenRouter/custom-Azure models that
         only resolve via aliases registered by
         ``pricing_registration`` at startup. **Skipped for image
         responses** — ``cost_per_token`` does not support ``ImageResponse``
         and would raise; the cost map for image-gen lives in different
         keys (``output_cost_per_image``) handled by ``completion_cost``.
    """
    cost = kwargs.get("response_cost")
    if cost is not None:
        try:
            value = float(cost)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value

    hidden = getattr(response_obj, "_hidden_params", None) or {}
    if isinstance(hidden, dict):
        cost = hidden.get("response_cost")
        if cost is not None:
            try:
                value = float(cost)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value

    try:
        value = float(litellm.completion_cost(completion_response=response_obj))
        if value > 0:
            return value
    except Exception as exc:
        if is_image:
            # Image-gen path: OpenRouter's image responses can omit
            # ``usage.cost`` and LiteLLM's ``default_image_cost_calculator``
            # then *raises* (no cost map for OpenRouter image models).
            # Bail out with a warning rather than falling through to
            # cost_per_token (which is also incompatible with ImageResponse).
            logger.warning(
                "[TokenTracking] completion_cost failed for image model=%s "
                "(provider may have omitted usage.cost). Debiting 0. "
                "Cause: %s",
                model,
                exc,
            )
            return 0.0
        logger.debug(
            "[TokenTracking] completion_cost failed for model=%s: %s", model, exc
        )

    if is_image:
        # Never call cost_per_token for ImageResponse — keys mismatch and
        # the function is documented chat-only.
        return 0.0

    if model and (prompt_tokens > 0 or completion_tokens > 0):
        try:
            prompt_cost, completion_cost = litellm.cost_per_token(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            value = float(prompt_cost) + float(completion_cost)
            if value > 0:
                return value
        except Exception as exc:
            logger.debug(
                "[TokenTracking] cost_per_token failed for model=%s: %s", model, exc
            )

    return 0.0


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
            logger.debug(
                "[TokenTracking] async_log_success_event fired but no accumulator in context"
            )
            return

        # Detect image generation responses — they have a different usage
        # shape (ImageUsage with input_tokens/output_tokens) and require a
        # different cost-extraction path. We probe by class name to avoid a
        # hard import dependency on litellm internals.
        response_cls = type(response_obj).__name__
        is_image = response_cls == "ImageResponse"

        usage = getattr(response_obj, "usage", None)
        if not usage:
            logger.debug(
                "[TokenTracking] async_log_success_event fired but response has no usage data"
            )
            return

        if is_image:
            # ``ImageUsage`` exposes ``input_tokens`` / ``output_tokens``
            # (not prompt_tokens/completion_tokens). Several providers
            # populate only one or neither (e.g. OpenRouter's gpt-image-1
            # passes through `input_tokens` from the prompt but no
            # completion); fall through gracefully to 0.
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = (
                getattr(usage, "total_tokens", 0) or prompt_tokens + completion_tokens
            )
            call_kind = "image_generation"
        else:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0
            call_kind = "chat"

        model = kwargs.get("model", "unknown")

        cost_usd = _extract_cost_usd(
            kwargs=kwargs,
            response_obj=response_obj,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            is_image=is_image,
        )
        cost_micros = round(cost_usd * 1_000_000) if cost_usd > 0 else 0

        if cost_micros == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            logger.warning(
                "[TokenTracking] No cost resolved for model=%s prompt=%d completion=%d "
                "kind=%s — debiting 0. Register pricing via pricing_registration or YAML "
                "input_cost_per_token/output_cost_per_token (or rely on response_cost "
                "for image generation).",
                model,
                prompt_tokens,
                completion_tokens,
                call_kind,
            )

        acc.add(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_micros=cost_micros,
            call_kind=call_kind,
        )
        logger.info(
            "[TokenTracking] Captured: model=%s kind=%s prompt=%d completion=%d total=%d "
            "cost=$%.6f (%d micros) (accumulator now has %d calls)",
            model,
            call_kind,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost_usd,
            cost_micros,
            len(acc.calls),
        )


token_tracker = TokenTrackingCallback()


# ---------------------------------------------------------------------------
# Persistence helper
# ---------------------------------------------------------------------------


async def record_token_usage(
    session: AsyncSession,
    *,
    usage_type: str,
    search_space_id: int,
    user_id: UUID,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_micros: int = 0,
    model_breakdown: dict[str, Any] | None = None,
    call_details: dict[str, Any] | None = None,
    thread_id: int | None = None,
    message_id: int | None = None,
) -> TokenUsage | None:
    """Persist a single ``TokenUsage`` row.

    Returns the record on success, ``None`` if persistence failed (the
    failure is logged but never propagated so callers don't need to
    wrap this in try/except).
    """
    try:
        record = TokenUsage(
            usage_type=usage_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_micros=cost_micros,
            model_breakdown=model_breakdown,
            call_details=call_details,
            thread_id=thread_id,
            message_id=message_id,
            search_space_id=search_space_id,
            user_id=user_id,
        )
        session.add(record)
        logger.debug(
            "[TokenTracking] recorded %s usage: prompt=%d completion=%d total=%d cost_micros=%d",
            usage_type,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost_micros,
        )
        return record
    except Exception:
        logger.warning(
            "[TokenTracking] failed to record %s token usage",
            usage_type,
            exc_info=True,
        )
        return None
