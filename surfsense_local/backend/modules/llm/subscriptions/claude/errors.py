from datetime import UTC, datetime

from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    SystemMessage,
)

from modules.llm.providers.openai_responses.errors import (
    PlanLimitError,
    SignInRequiredError,
)
from modules.llm.subscriptions.claude.extra_usage import refused


class ClaudeSignInRequiredError(SignInRequiredError):
    """Claude Code is gone or signed out: fixed in a terminal, not in SurfSense."""


class ClaudePlanLimitError(PlanLimitError):
    """The Claude plan's usage limit is reached; it resets on its own."""


class ClaudeTooOldError(Exception):
    """The Claude Code found is older than MIN_VERSION: updated in a terminal, not in SurfSense."""


class ClaudeRunError(Exception):
    """Claude Code ended a run with an error that is not the plan's or the sign-in's."""


def _limit_reached(resets_at: int | None) -> ClaudePlanLimitError:
    if resets_at is None:
        return ClaudePlanLimitError("the Claude plan's usage limit is reached")
    when = datetime.fromtimestamp(resets_at, UTC).isoformat()
    return ClaudePlanLimitError(
        f"the Claude plan's usage limit is reached until {when}"
    )


def failure_of(
    message: object, *, proxy_refusal: Exception | None = None
) -> Exception | None:
    """The error a message from Claude Code means for SurfSense, if any.

    `proxy_refusal` is the egress refusal standing when Claude Code retries:
    it retries a refused tunnel ten times instead of failing, so its first
    retry with a Claude host off is that refusal.
    """
    if isinstance(message, AssistantMessage):
        if message.error == "authentication_failed":
            return ClaudeSignInRequiredError("Claude Code has to sign in again")
        if message.error == "rate_limit":
            return _limit_reached(None)
    if isinstance(message, RateLimitEvent) and refused(message.rate_limit_info):
        return _limit_reached(message.rate_limit_info.resets_at)
    if isinstance(message, SystemMessage) and message.subtype == "api_retry":
        return proxy_refusal
    if isinstance(message, ResultMessage) and message.is_error:
        detail = "; ".join(message.errors or []) or message.subtype
        return ClaudeRunError(f"Claude Code failed: {detail}")
    return None
