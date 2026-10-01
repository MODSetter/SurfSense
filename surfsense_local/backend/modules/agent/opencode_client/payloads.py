from typing import Any

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    """One frame of opencode's event stream: what happened, and its details as sent.

    Fields opencode adds in a later release are kept rather than refused, so a
    pin bump cannot break parsing; only what SurfSense reads is named.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    type: str
    properties: dict[str, Any] = {}
