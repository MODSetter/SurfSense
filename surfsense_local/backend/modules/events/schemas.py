import enum

from pydantic import BaseModel


class EventKind(enum.StrEnum):
    """The category of change, and the SSE event name the client listens for."""

    DOCUMENTS = "documents"
    ARTIFACTS = "artifacts"
    FOLDERS = "folders"


class InternalEvent(BaseModel):
    """A notice that some rows changed, fanned out as one SSE event.

    The worker posts its own; the API builds one for a change it made itself.
    """

    workspace_id: int
    kind: EventKind
    ids: list[int]
    status: str
