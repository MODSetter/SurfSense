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

from app.observability.analytics import posthog as ph_analytics

if TYPE_CHECKING:
    from app.auth.context import AuthContext
    from app.services.token_tracking_service import TurnTokenAccumulator

logger = logging.getLogger(__name__)


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
    if not ph_analytics.is_enabled() or not user_id:
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
        ph_analytics.capture_for(auth_context, "chat_turn_completed", props, groups=groups)
    else:
        ph_analytics.capture(
            "chat_turn_completed",
            distinct_id=user_id,
            properties=props,
            groups=groups,
        )
