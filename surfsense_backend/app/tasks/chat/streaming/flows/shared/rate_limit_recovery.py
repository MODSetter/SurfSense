"""Shared steps for the in-stream provider rate-limit recovery loop.

Both flows wrap ``run_stream_loop`` with a flow-specific ``recover`` closure;
the *guard*, the *auto-pin reroute*, and the *post-recovery telemetry* are the
same on both sides and live here so behaviour can't drift.

The orchestrator owns the parts that genuinely diverge:

  * cancelling the title task (new_chat only),
  * passing ``mentioned_document_ids`` to ``build_main_agent_for_thread``,
  * the log prefix (``stream_new_chat`` vs ``stream_resume``).
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import end_turn
from app.observability import otel as ot
from app.services.auto_model_pin_service import (
    mark_runtime_cooldown,
    resolve_or_get_pinned_llm_config_id,
)
from app.tasks.chat.streaming.errors.classifier import (
    is_provider_rate_limited,
    log_chat_stream_error,
)


def can_recover_provider_rate_limit(
    exc: BaseException,
    *,
    first_event_seen: bool,
    runtime_rate_limit_recovered: bool,
    requested_llm_config_id: int,
    current_llm_config_id: int,
) -> bool:
    """Guard: only the first auto-pin → provider-rate-limited failure recovers.

    All conditions must hold:

      * ``runtime_rate_limit_recovered is False`` — at most one recovery per turn.
      * ``requested_llm_config_id == 0`` — caller opted into auto-pin (id=0).
      * ``current_llm_config_id < 0`` — currently on a YAML config (the only
        kind the auto-pin pool draws from).
      * ``first_event_seen is False`` — we haven't sent any SSE to the user yet,
        so a silent rebuild + retry is invisible.
      * The exception is provider-side rate-limited (HTTP 429 or known shape).
    """
    return (
        not runtime_rate_limit_recovered
        and requested_llm_config_id == 0
        and current_llm_config_id < 0
        and not first_event_seen
        and is_provider_rate_limited(exc)
    )


async def reroute_to_next_auto_pin(
    session: AsyncSession,
    *,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    current_llm_config_id: int,
    requires_image_input: bool,
) -> int:
    """Release lock, cool down the failing config, pick a new auto-pin id.

    Returns the new ``llm_config_id``. ``end_turn`` is called because the failed
    attempt may still hold the per-thread busy mutex (middleware teardown can
    lag behind raised provider errors) — the same-request retry would otherwise
    bounce on ``BusyError``.
    """
    end_turn(str(chat_id))
    mark_runtime_cooldown(current_llm_config_id, reason="provider_rate_limited")
    pinned = await resolve_or_get_pinned_llm_config_id(
        session,
        thread_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
        selected_llm_config_id=0,
        exclude_config_ids={current_llm_config_id},
        requires_image_input=requires_image_input,
    )
    return pinned.resolved_llm_config_id


def log_rate_limit_recovered(
    *,
    flow: Literal["new", "regenerate", "resume"],
    request_id: str | None,
    chat_id: int,
    workspace_id: int,
    user_id: str | None,
    previous_config_id: int,
    new_config_id: int,
) -> None:
    """Emit the OTEL event + structured ``[chat_stream_error]`` log line."""
    ot.add_event(
        "chat.rate_limit.recovered",
        {
            "recovery.reason": "provider_rate_limited",
            "recovery.previous_config_id": previous_config_id,
            "recovery.fallback_config_id": new_config_id,
        },
    )
    log_chat_stream_error(
        flow=flow,
        error_kind="rate_limited",
        error_code="RATE_LIMITED",
        severity="info",
        is_expected=True,
        request_id=request_id,
        thread_id=chat_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message=(
            "Auto-pinned model hit runtime rate limit; switched to "
            "another eligible model and retried."
        ),
        extra={
            "auto_runtime_recover": True,
            "previous_config_id": previous_config_id,
            "fallback_config_id": new_config_id,
        },
    )
