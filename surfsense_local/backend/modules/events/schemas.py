import enum

from pydantic import BaseModel


class EventKind(enum.StrEnum):
    """The category of change, and the SSE event name the client listens for."""

    DOCUMENTS = "documents"  # v1; artifacts join later


class InternalEvent(BaseModel):
    """The worker's notice that some rows changed, fanned out as one SSE event."""

    workspace_id: int
    kind: EventKind
    ids: list[int]
    status: str
