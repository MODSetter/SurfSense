"""The chat frame that says where a plan stands after a reply, from a chat or an agent turn alike."""

from typing import Any

from modules.llm.providers.types import PlanUsage


def plan_usage_frame(usage: PlanUsage) -> dict[str, Any]:
    return {
        "type": "plan-extra-usage",
        "using": usage.using_extra,
        "resets_at": usage.resets_at,
    }
