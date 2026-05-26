"""``ManualTriggerConfig`` — config for the ``manual`` trigger type (empty in v1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ManualTriggerConfig(BaseModel):
    """Config for the UI-driven ``manual`` trigger.

    Validated against ``AutomationTrigger.config`` whenever the
    persisted ``type`` is ``manual``. v1 carries no configurable
    fields — the "Run now" affordance simply fires this trigger with
    an empty config object. The model exists so the registry dispatch
    is uniform across all trigger types.

    Future versions may add fields here (e.g., a fixed prompt to
    pre-fill the run dialog with) without breaking v1 payloads.
    """

    model_config = ConfigDict(extra="forbid")
