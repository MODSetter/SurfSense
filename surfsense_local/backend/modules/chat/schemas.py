from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.chat.budget import QUESTION_CHARS
from modules.chat.models import MessageRole
from modules.source_scope.schemas import SourceScope

ThreadTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
# The question's share of the window (budget.py), refused here before any
# model is resolved or retrieval runs.
MessageText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=QUESTION_CHARS),
]
DocumentId = Annotated[int, Field(gt=0)]
MAX_IMAGES = 4
# Base64 of the 10 MB decoded cap, checked before anything is decoded.
_MAX_IMAGE_BASE64 = -(-10 * 1024 * 1024 // 3) * 4


class ImageUpload(BaseModel):
    """One attached image. `mime` is the client's word only: the bytes decide."""

    mime: str | None = None
    data: Annotated[str, Field(min_length=1, max_length=_MAX_IMAGE_BASE64)]


class ThreadCreate(BaseModel):
    """Fields a client supplies when opening a thread.

    `source_scope` is the new chat's drafted ticks; omitted, the thread uses
    every source.
    """

    title: ThreadTitle = "New chat"
    source_scope: SourceScope | None = None


class ThreadUpdate(BaseModel):
    """Fields a client may change on an existing thread."""

    title: ThreadTitle


class RunStateRead(BaseModel):
    """Where a thread's reply stands: `queued` with its place in line, `running`,
    or `needs-approval` while it waits on the user."""

    state: Literal["queued", "running", "needs-approval"]
    position: int | None = None


class ThreadRead(BaseModel):
    """A thread as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    title: str | None
    uses_agent: bool
    # None: the thread never stored ticks and uses every source.
    source_scope: SourceScope | None
    created_at: datetime
    updated_at: datetime
    # Whether a reply is being generated for it right now.
    running: bool = False
    # Where that reply stands; None when nothing is being generated.
    run_state: RunStateRead | None = None


class MessageCreate(BaseModel):
    """The user's turn; the assistant's is streamed, not posted.

    `source_scope` is resolved on the server, stored on the thread and used for
    this turn; omitted, the thread's stored scope is used. `document_ids` is the
    older explicit list, kept for plugins and older clients: used only when no
    `source_scope` is sent, it must name ready sources, and an empty list
    retrieves nothing. `images` reach only a model that reads them; any other
    gets a 409. `thinking` off asks for the answer with no trace, which only the
    local runtime can be told. `retry_of` names the thread's latest reply when
    it failed or was cut off, which this turn replaces.
    """

    text: MessageText
    source_scope: SourceScope | None = None
    document_ids: Annotated[list[DocumentId], Field(max_length=1000)] | None = None
    images: Annotated[list[ImageUpload], Field(max_length=MAX_IMAGES)] = []
    thinking: bool = True
    retry_of: Annotated[int, Field(gt=0)] | None = None


class MessageRead(BaseModel):
    """A stored turn; `content` carries the text and any citations for the UI.

    An agent thread's turns come from opencode, whose ids are strings.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int | str
    role: MessageRole
    content: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None
