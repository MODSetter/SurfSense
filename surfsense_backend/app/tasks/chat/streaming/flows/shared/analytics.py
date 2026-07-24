"""PostHog chat-turn analytics for streaming flows.

Emits a single authoritative ``chat_turn_completed`` product event per turn,
shared by the new-chat and resume orchestrators so every chat source (web,
desktop, PAT scripts, gateway, automations) is tracked identically —
including sources the frontend can never observe. No-op when PostHog is
unconfigured.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.config import config
from app.observability import analytics

if TYPE_CHECKING:
    from app.auth.context import AuthContext
    from app.services.token_tracking_service import TurnTokenAccumulator

logger = logging.getLogger(__name__)


def build_llm_callback_handler(
    *,
    distinct_id: str | None,
    trace_id: str | None,
    properties: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
) -> Any | None:
    """Build a PostHog LangChain ``CallbackHandler`` for a chat turn.

    Attaching this to the LangGraph ``config["callbacks"]`` captures the full
    agent trace tree ($ai_trace / $ai_span / $ai_generation) — every LLM call,
    tool, subagent, and retriever — joined to the ``chat_turn_completed`` event
    via ``trace_id`` (the turn id) and grouped per conversation via
    ``$ai_session_id`` (in ``properties``).

    Returns ``None`` when PostHog is disabled or the package/handler is
    unavailable, so callers can simply skip attaching callbacks. ``privacy_mode``
    (default on) suppresses prompt/completion bodies — chat content includes
    users' private documents.
    """
    client_obj = analytics.get_client()
    if client_obj is None or not distinct_id:
        return None

    try:
        from posthog.ai.langchain import CallbackHandler

        return CallbackHandler(
            client=client_obj,
            distinct_id=distinct_id,
            trace_id=trace_id,
            properties=properties or {},
            privacy_mode=config.POSTHOG_AI_PRIVACY_MODE,
            groups=groups,
        )
    except Exception:
        logger.debug("PostHog LLM callback handler unavailable", exc_info=True)
        return None


def capture_chat_turn_completed(
    *,
    flow: str,
    outcome: str,
    error_category: str | None,
    workspace_id: int,
    chat_id: int,
    user_id: str | None,
    auth_context: AuthContext | None,
    agent_mode: str,
    client_platform: str,
    filesystem_mode: str,
    turn_id: str | None,
    request_id: str | None,
    duration_ms: int,
    accumulator: TurnTokenAccumulator,
) -> None:
    """Capture ``chat_turn_completed``. Best-effort; never raises."""
    if not analytics.is_enabled() or not user_id:
        return

    props: dict[str, Any] = {
        "flow": flow,
        "outcome": outcome,
        "error_category": error_category,
        "workspace_id": workspace_id,
        "chat_id": chat_id,
        "agent_mode": agent_mode,
        "client_platform": client_platform,
        "filesystem_mode": filesystem_mode,
        "turn_id": turn_id,
        "request_id": request_id,
        "duration_ms": duration_ms,
        # Cost is micro-USD (integer), matching TurnTokenAccumulator; do not
        # convert to float dollars.
        "total_tokens": accumulator.grand_total,
        "prompt_tokens": accumulator.total_prompt_tokens,
        "completion_tokens": accumulator.total_completion_tokens,
        "cost_micros": accumulator.total_cost_micros,
    }
    groups = {"workspace": str(workspace_id)}

    if auth_context is not None:
        analytics.capture_for(
            auth_context, "chat_turn_completed", props, groups=groups
        )
    else:
        analytics.capture(
            "chat_turn_completed",
            distinct_id=user_id,
            properties=props,
            groups=groups,
        )
