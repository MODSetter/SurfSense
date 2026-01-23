"""
Pydantic schemas for chat session state (live collaboration).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RespondingUser(BaseModel):
    """The user that the AI is currently responding to."""

    id: UUID
    display_name: str | None = None
    email: str

    model_config = ConfigDict(from_attributes=True)


class ChatSessionStateResponse(BaseModel):
    """Current session state for a chat thread."""

    id: int
    thread_id: int
    responding_to: RespondingUser | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
