from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

from modules.chat.models import MessageRole

ThreadTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ThreadCreate(BaseModel):
    """Fields a client supplies when opening a thread."""

    title: ThreadTitle | None = None


class ThreadRead(BaseModel):
    """A thread as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    """The user's turn; the assistant's is streamed, not posted."""

    text: MessageText


class MessageRead(BaseModel):
    """A stored turn; `content` carries the text and any citations for the UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: dict[str, Any]
    created_at: datetime
