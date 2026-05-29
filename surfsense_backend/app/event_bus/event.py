"""The ``Event`` value object — the only shape that crosses the bus.

An immutable fact: something named happened, with this payload, in this space,
at this time. JSON round-trippable so a subscriber can queue it to a worker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _new_event_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Event(BaseModel):
    """A published domain fact.

    ``event_type`` is a dotted namespace (``document.indexed``, etc). ``payload`` is
    JSON-serializable. ``search_space_id`` scopes delivery. ``event_id`` and
    ``occurred_at`` are engine-stamped.
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    search_space_id: int
    event_id: str = Field(default_factory=_new_event_id)
    occurred_at: datetime = Field(default_factory=_now)
