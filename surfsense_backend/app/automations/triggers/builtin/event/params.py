"""``EventTriggerParams`` — params for the ``event`` trigger type."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventTriggerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(
        ...,
        min_length=1,
        description="Event type to listen for.",
        examples=["document.indexed"],
    )
    filter: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON filter matched against the event payload.",
        examples=[{"document_type": "FILE"}],
    )
