from datetime import UTC, datetime

from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    SystemMessage,
)

from modules.egress.service import EgressDeniedError
from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)

ANTHROPIC_HOST = "api.anthropic.com"


class ClaudeRunError(Exception):
    """Claude Code ended a run with an error that is not the plan's or the sign-in's."""


def _limit_reached(resets_at: int | None) -> PlanLimitError:
    if resets_at is None:
        return PlanLimitError("the Claude plan's usage limit is reached")
    when = datetime.fromtimestamp(resets_at, UTC).isoformat()
    return PlanLimitError(f"the Claude plan's usage limit is reached until {when}")


def failure_of(message: object, *, proxy_refused: bool = False) -> Exception | None:
    """The error a message from Claude Code means for SurfSense, if any.

    `proxy_refused` says SurfSense's proxy refused this run a tunnel: Claude Code
    retries that ten times instead of failing, so its first retry is the refusal.
    """
    if isinstance(message, AssistantMessage):
        if message.error == "authentication_failed":
            return SignInRequiredError("Claude Code has to sign in again")
        if message.error == "rate_limit":
            return _limit_reached(None)
    if (
        isinstance(message, RateLimitEvent)
        and message.rate_limit_info.status == "rejected"
    ):
        return _limit_reached(message.rate_limit_info.resets_at)
    if (
        isinstance(message, SystemMessage)
        and message.subtype == "api_retry"
        and proxy_refused
    ):
        return EgressDeniedError(f"host:{ANTHROPIC_HOST}", host=ANTHROPIC_HOST)
    if isinstance(message, ResultMessage) and message.is_error:
        detail = "; ".join(message.errors or []) or message.subtype
        return ClaudeRunError(f"Claude Code failed: {detail}")
    return None
