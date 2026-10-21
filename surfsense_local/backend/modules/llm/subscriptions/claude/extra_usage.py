"""Where the Claude plan stands after a reply: within its limit, or past it on extra usage billed apart.

Read from how Claude Code 2.1.301 builds its rate-limit event from Anthropic's
headers: past the plan's limit its `status` is `rejected`, and `isUsingOverage`
(the plan refused, extra usage allowed) or `overageInUse` (the
`anthropic-ratelimit-unified-overage-in-use` header) says extra usage pays, so
Claude Code goes on answering. Only within the plan was seen on a live account.
"""

from claude_agent_sdk import RateLimitEvent, RateLimitInfo

from modules.llm.providers.types import PlanUsage


def on_extra_usage(info: RateLimitInfo) -> bool:
    return (
        info.raw.get("isUsingOverage") is True or info.raw.get("overageInUse") is True
    )


def refused(info: RateLimitInfo) -> bool:
    """Claude Code's own test of a reply that cannot go on: the plan refused, and no extra usage pays."""
    return info.status == "rejected" and not on_extra_usage(info)


def plan_usage(message: object) -> PlanUsage | None:
    """None for any other message, and for a refusal, which ends the reply as the plan's limit."""
    if not isinstance(message, RateLimitEvent) or refused(message.rate_limit_info):
        return None
    info = message.rate_limit_info
    return PlanUsage(on_extra_usage(info), info.resets_at)
