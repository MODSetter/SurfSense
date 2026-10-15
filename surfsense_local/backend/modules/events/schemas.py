import enum

from pydantic import BaseModel


class EventKind(enum.StrEnum):
    """The category of change, and the SSE event name the client listens for."""

    DOCUMENTS = "documents"
    ARTIFACTS = "artifacts"
    CHAT_RUNS = "chat-runs"
    FOLDERS = "folders"


class Progress(BaseModel):
    """How far a row's long job has come, in seconds of its media: a
    recording's transcription."""

    done_s: float
    total_s: float


class InternalEvent(BaseModel):
    """A notice that some rows changed, fanned out as one SSE event.

    The worker posts its own; the API builds one for a change it made itself.
    """

    workspace_id: int
    kind: EventKind
    ids: list[int]
    status: str
    # Sent once per step of a long job and never stored, like chat's
    # prompt-progress frame; a late listener reads the row instead.
    progress: Progress | None = None
