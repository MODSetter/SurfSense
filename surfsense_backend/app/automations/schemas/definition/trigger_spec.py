"""``TriggerSpec`` — one entry in the envelope's ``triggers`` array."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TriggerSpec(BaseModel):
    """One trigger attached to an automation, as it appears in the definition.

    The envelope keeps ``config`` as an untyped JSON object on purpose
    — the per-type config schemas live in
    ``app.automations.schemas.triggers`` and are dispatched at
    validation time by looking up ``type`` in the trigger registry.

    This mirrors the design's "definitions are pure data" principle:
    the envelope describes shape, the registry resolves names to
    behaviour.
    """

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        ...,
        description=(
            "Trigger-type discriminator (e.g., ``schedule``, ``manual``). "
            "Resolved against the trigger registry."
        ),
        min_length=1,
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Trigger-type-specific config. Validated against the "
            "registered ``TriggerDefinition.config_schema`` for "
            "``type`` at definition-save time."
        ),
    )
