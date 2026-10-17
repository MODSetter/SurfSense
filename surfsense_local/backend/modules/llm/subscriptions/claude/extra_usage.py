"""Where the Claude plan stands after a reply: within its limit, or past it on extra usage billed apart.

Claude Code sends a rate-limit event with each reply; `isUsingOverage` says extra
usage pays, per the SDK. Measured only off (`overageStatus: rejected`,
`org_level_disabled`), as a plan using it was not at hand.
"""

from claude_agent_sdk import RateLimitEvent

from modules.llm.providers.types import PlanUsage


def plan_usage(message: object) -> PlanUsage | None:
    """None for any other message, and for a refusal, which ends the reply as the plan's limit."""
    if (
        not isinstance(message, RateLimitEvent)
        or message.rate_limit_info.status == "rejected"
    ):
        return None
    info = message.rate_limit_info
    return PlanUsage(info.raw.get("isUsingOverage") is True, info.resets_at)
