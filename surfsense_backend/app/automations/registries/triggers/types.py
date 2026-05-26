"""``TriggerDefinition`` dataclass — declarative trigger metadata, no handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TriggerDefinition:
    """A trigger type the dispatcher knows how to fire.

    Triggers are purely declarative: the dispatcher (a single
    process-wide component, not a per-type handler) reads the
    ``automation_triggers`` table and decides when each row should
    fire. The trigger's job here is to declare its input/output
    contract:

    - ``config_schema``: JSON Schema for the persisted
      ``AutomationTrigger.config`` — used by the form editor and
      validated on save.
    - ``payload_schema``: JSON Schema for the payload the dispatcher
      will deliver to the executor at fire time (e.g., a schedule
      trigger emits ``fired_at`` / ``scheduled_for`` /
      ``last_fired_at``).

    No ``handler`` field — firing is a dispatcher responsibility,
    not a per-trigger one. This keeps the dispatcher single and
    leaves trigger types as pure metadata.
    """

    type: str
    description: str
    config_schema: dict[str, Any]
    payload_schema: dict[str, Any]
