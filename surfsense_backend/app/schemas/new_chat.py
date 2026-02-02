"""
Pydantic schemas for the new chat feature with assistant-ui integration.

These schemas follow the assistant-ui ThreadHistoryAdapter pattern:
- ThreadRecord: id, title, archived, createdAt, updatedAt
- MessageRecord: id, threadId, role, content, createdAt
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db import ChatVisibility, NewChatMessageRole

from .base import IDModel, TimestampModel

# =============================================================================
# Message Schemas
# =============================================================================


class NewChatMessageBase(BaseModel):
    """Base schema for new chat messages."""

    role: NewChatMessageRole
    content: Any  # JSONB content - can be text, tool calls, etc.


class NewChatMessageCreate(NewChatMessageBase):
    """Schema for creating a new message."""

    thread_id: int


class NewChatMessageRead(NewChatMessageBase, IDModel, TimestampModel):
    """Schema for reading a message."""

    thread_id: int
    author_id: UUID | None = None
    author_display_name: str | None = None
    author_avatar_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class NewChatMessageAppend(BaseModel):
    """
    Schema for appending a message via the history adapter.
    This is the format assistant-ui sends when calling append().
    """

    role: str  # Accept string and validate in route handler
    content: Any


# =============================================================================
# Thread Schemas
# =============================================================================


class NewChatThreadBase(BaseModel):
    """Base schema for new chat threads."""

    title: str = Field(default="New Chat", max_length=500)
    archived: bool = False


class NewChatThreadCreate(NewChatThreadBase):
    """Schema for creating a new thread."""

    search_space_id: int
    # Visibility defaults to PRIVATE, but can be set on creation
    visibility: ChatVisibility = ChatVisibility.PRIVATE


class NewChatThreadUpdate(BaseModel):
    """Schema for updating a thread."""

    title: str | None = None
    archived: bool | None = None


class NewChatThreadVisibilityUpdate(BaseModel):
    """Schema for updating thread visibility/sharing settings."""

    visibility: ChatVisibility


class NewChatThreadRead(NewChatThreadBase, IDModel):
    """
    Schema for reading a thread (matches assistant-ui ThreadRecord).
    """

    search_space_id: int
    visibility: ChatVisibility
    created_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NewChatThreadWithMessages(NewChatThreadRead):
    """Schema for reading a thread with its messages."""

    messages: list[NewChatMessageRead] = []
    has_comments: bool = False


# =============================================================================
# History Adapter Response Schemas
# =============================================================================


class ThreadHistoryLoadResponse(BaseModel):
    """
    Response format for the ThreadHistoryAdapter.load() method.
    Returns messages array for the current thread.
    """

    messages: list[NewChatMessageRead]


class ThreadListItem(BaseModel):
    """
    Thread list item for sidebar display.
    Matches assistant-ui ThreadListPrimitive expected format.
    """

    id: int
    title: str
    archived: bool
    visibility: ChatVisibility
    created_by_id: UUID | None = None
    is_own_thread: bool = False
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ThreadListResponse(BaseModel):
    """Response containing list of threads for the sidebar."""

    threads: list[ThreadListItem]
    archived_threads: list[ThreadListItem]


# =============================================================================
# Chat Request Schemas (for deep agent)
# =============================================================================


class ChatMessage(BaseModel):
    """A single message in the chat history."""

    role: str  # "user" or "assistant"
    content: str


class ChatAttachment(BaseModel):
    """An attachment with its extracted content for chat context."""

    id: str  # Unique attachment ID
    name: str  # Original filename
    type: str  # Attachment type: document, image, audio
    content: str  # Extracted markdown content from the file


class NewChatRequest(BaseModel):
    """Request schema for the deep agent chat endpoint."""

    chat_id: int
    user_query: str
    search_space_id: int
    messages: list[ChatMessage] | None = None  # Optional chat history from frontend
    attachments: list[ChatAttachment] | None = (
        None  # Optional attachments with extracted content
    )
    mentioned_document_ids: list[int] | None = (
        None  # Optional document IDs mentioned with @ in the chat
    )
    mentioned_surfsense_doc_ids: list[int] | None = (
        None  # Optional SurfSense documentation IDs mentioned with @ in the chat
    )


class RegenerateRequest(BaseModel):
    """
    Request schema for regenerating an AI response.

    This supports two operations:
    1. Edit: Provide a new user_query to replace the last user message and regenerate
    2. Reload: Leave user_query empty to regenerate the last AI response with the same query

    Both operations rewind the LangGraph checkpointer to the appropriate state.
    """

    search_space_id: int
    user_query: str | None = (
        None  # New user query (for edit). None = reload with same query
    )
    attachments: list[ChatAttachment] | None = None
    mentioned_document_ids: list[int] | None = None
    mentioned_surfsense_doc_ids: list[int] | None = None


# =============================================================================
# Public Chat Snapshot Schemas
# =============================================================================


class PublicChatSnapshotCreateResponse(BaseModel):
    """Response after creating a public chat snapshot."""

    snapshot_id: int
    share_token: str
    public_url: str
    is_new: bool


class PublicChatSnapshotInfo(BaseModel):
    """Info about a single public chat snapshot."""

    id: int
    share_token: str
    public_url: str
    created_at: datetime
    message_count: int


class PublicChatSnapshotListResponse(BaseModel):
    """List of public chat snapshots for a thread."""

    snapshots: list[PublicChatSnapshotInfo]


class PublicChatSnapshotDetail(BaseModel):
    """Public chat snapshot with thread context."""

    id: int
    share_token: str
    public_url: str
    created_at: datetime
    message_count: int
    thread_id: int
    thread_title: str


class PublicChatSnapshotsBySpaceResponse(BaseModel):
    """List of public chat snapshots for a search space."""

    snapshots: list[PublicChatSnapshotDetail]


# =============================================================================
# Public Chat View Schemas (for unauthenticated access)
# =============================================================================


class PublicAuthor(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None


class PublicChatMessage(BaseModel):
    role: NewChatMessageRole
    content: Any
    author: PublicAuthor | None = None
    created_at: datetime


class PublicChatThread(BaseModel):
    title: str
    created_at: datetime


class PublicChatResponse(BaseModel):
    thread: PublicChatThread
    messages: list[PublicChatMessage]


class CloneResponse(BaseModel):
    """Response after cloning a public snapshot."""

    thread_id: int
    search_space_id: int
