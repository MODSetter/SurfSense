"""How OpenCode's Console serves its models, which models.dev cannot say.

models.dev records each model's native API, but the Console translates: "Every
API serves every paid and Go text model". Free-tier chat models answer a 403
outside OpenCode, "even with a Console API key".
https://opencode.ai/v2/docs/console/harnesses
"""

from typing import Any

__all__ = ["OPENCODE_CONSOLE_PROVIDERS", "console_call"]

OPENCODE_CONSOLE_PROVIDERS = frozenset({"opencode", "opencode-go"})

_FREE_MODEL_REASON = "OpenCode allows this free model only inside OpenCode"


def console_call(model: dict[str, Any]) -> dict[str, str] | None:
    """How a Console model is called. Price decides what is free, because
    `big-pickle` and `grok-code` cost nothing and have no `-free` in their ids."""
    cost = model.get("cost") or {}
    if cost.get("input") == 0 and cost.get("output") == 0:
        return {"unavailable": _FREE_MODEL_REASON}
    return None
