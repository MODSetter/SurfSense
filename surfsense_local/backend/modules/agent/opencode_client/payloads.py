from typing import Any

from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    """One frame of opencode's event stream: what happened, and its details as sent.

    Fields opencode adds in a later release are kept rather than refused, so a
    pin bump cannot break parsing; only what SurfSense reads is named. A
    session's events name it in `data.sessionID`; not every one names its folder.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    type: str
    # When opencode recorded it, in milliseconds.
    created: int | None = None
    data: dict[str, Any] = {}
