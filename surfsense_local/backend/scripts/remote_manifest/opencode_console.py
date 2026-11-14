"""How OpenCode's Console serves its models, which models.dev cannot say.

models.dev records each model's native API, but the Console translates: "Every
API serves every paid and Go text model".
https://opencode.ai/v2/docs/console/harnesses
"""

from typing import Any

from modules.llm.connections.opencode_free_models import (
    FREE_MODEL_REASON,
    ZEN_PROVIDER,
)

__all__ = ["console_call"]


def console_call(model: dict[str, Any], provider_id: str) -> dict[str, str] | None:
    """How a Console model is called. Price decides what is free, because
    `big-pickle` and `grok-code` cost nothing and have no `-free` in their ids."""
    cost = model.get("cost") or {}
    free = cost.get("input") == 0 and cost.get("output") == 0
    return (
        {"unavailable": FREE_MODEL_REASON}
        if free and provider_id == ZEN_PROVIDER
        else None
    )
