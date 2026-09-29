from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from modules.chat.models import MessageRole

ThreadTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
DocumentId = Annotated[int, Field(gt=0)]
MAX_IMAGES = 4
# Base64 of the 10 MB decoded cap, checked before anything is decoded.
_MAX_IMAGE_BASE64 = -(-10 * 1024 * 1024 // 3) * 4


class ImageUpload(BaseModel):
    """One attached image. `mime` is the client's word only: the bytes decide."""

    mime: str | None = None
    data: Annotated[str, Field(min_length=1, max_length=_MAX_IMAGE_BASE64)]


class ThreadCreate(BaseModel):
    """Fields a client supplies when opening a thread."""

    title: ThreadTitle = "New chat"


class ThreadUpdate(BaseModel):
    """Fields a client may change on an existing thread."""

    title: ThreadTitle


class ThreadRead(BaseModel):
    """A thread as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    """The user's turn; the assistant's is streamed, not posted.

    `document_ids` is the RAG scope for this turn. Omit it to search the whole
    workspace. An empty list retrieves nothing. `images` reach only a model
    that reads them; any other gets a 409.
    """

    text: MessageText
    document_ids: Annotated[list[DocumentId], Field(max_length=1000)] | None = None
    images: Annotated[list[ImageUpload], Field(max_length=MAX_IMAGES)] = []


class MessageRead(BaseModel):
    """A stored turn; `content` carries the text and any citations for the UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None
