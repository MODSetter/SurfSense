"""
Pydantic schemas for the new chat feature with assistant-ui integration.

These schemas follow the assistant-ui ThreadHistoryAdapter pattern:
- ThreadRecord: id, title, archived, createdAt, updatedAt
- MessageRecord: id, threadId, role, content, createdAt
"""

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db import ChatVisibility, NewChatMessageRole
from app.utils.user_message_multimodal import decode_base64_image, to_data_url

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


class TokenUsageSummary(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_breakdown: dict | None = None
    model_config = ConfigDict(from_attributes=True)


class NewChatMessageRead(NewChatMessageBase, IDModel, TimestampModel):
    """Schema for reading a message."""

    thread_id: int
    author_id: UUID | None = None
    author_display_name: str | None = None
    author_avatar_url: str | None = None
    token_usage: TokenUsageSummary | None = None
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


class LocalFilesystemMountPayload(BaseModel):
    mount_id: str
    root_path: str


MAX_NEW_CHAT_IMAGE_BYTES = 8 * 1024 * 1024
MAX_NEW_CHAT_IMAGES = 4


class NewChatUserImagePart(BaseModel):
    """One inline image for a user turn (raw base64 body, no data: URL prefix)."""

    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(..., min_length=1)

    @field_validator("data")
    @classmethod
    def _validate_payload(cls, v: str) -> str:
        decode_base64_image(v, max_bytes=MAX_NEW_CHAT_IMAGE_BYTES)
        return v

    def as_data_url(self) -> str:
        return to_data_url(self.media_type, self.data)


class NewChatRequest(BaseModel):
    """Request schema for the deep agent chat endpoint."""

    chat_id: int
    user_query: str
    search_space_id: int
    messages: list[ChatMessage] | None = None  # Optional chat history from frontend
    mentioned_document_ids: list[int] | None = (
        None  # Optional document IDs mentioned with @ in the chat
    )
    mentioned_surfsense_doc_ids: list[int] | None = (
        None  # Optional SurfSense documentation IDs mentioned with @ in the chat
    )
    disabled_tools: list[str] | None = (
        None  # Optional list of tool names the user has disabled from the UI
    )
    filesystem_mode: Literal["cloud", "desktop_local_folder"] = "cloud"
    client_platform: Literal["web", "desktop"] = "web"
    local_filesystem_mounts: list[LocalFilesystemMountPayload] | None = None
    user_images: list[NewChatUserImagePart] | None = Field(
        default=None,
        description="Optional images for this user turn",
    )

    @model_validator(mode="after")
    def _require_text_or_images(self) -> Self:
        has_text = bool(self.user_query.strip())
        has_images = bool(self.user_images)
        if not has_text and not has_images:
            raise ValueError("Provide non-empty user_query and/or user_images")
        if self.user_images is not None and len(self.user_images) > MAX_NEW_CHAT_IMAGES:
            raise ValueError(f"At most {MAX_NEW_CHAT_IMAGES} images allowed")
        return self


class RegenerateRequest(BaseModel):
    """
    Request schema for regenerating an AI response.

    This supports two operations:
    1. Edit: Provide a new user_query to replace the last user message and regenerate
    2. Reload: Leave user_query empty to regenerate the last AI response with the same query

    Both operations rewind the LangGraph checkpointer to the appropriate state.

    For edit, optional user_images (when not None) replaces image URLs resolved from
    checkpoint/DB so the client can send the full user turn (text and/or images).
    """

    search_space_id: int
    user_query: str | None = (
        None  # New user query (for edit). None = reload with same query
    )
    mentioned_document_ids: list[int] | None = None
    mentioned_surfsense_doc_ids: list[int] | None = None
    disabled_tools: list[str] | None = None
    filesystem_mode: Literal["cloud", "desktop_local_folder"] = "cloud"
    client_platform: Literal["web", "desktop"] = "web"
    local_filesystem_mounts: list[LocalFilesystemMountPayload] | None = None
    user_images: list[NewChatUserImagePart] | None = Field(
        default=None,
        description="If set, use these images for the regenerated turn (edit); overrides checkpoint/DB",
    )

    @model_validator(mode="after")
    def _validate_regenerate_user_images(self) -> Self:
        if self.user_images is not None and len(self.user_images) > MAX_NEW_CHAT_IMAGES:
            raise ValueError(f"At most {MAX_NEW_CHAT_IMAGES} images allowed")
        return self


# =============================================================================
# Agent Tools Schemas
# =============================================================================


class AgentToolInfo(BaseModel):
    """Schema for a single agent tool's public metadata."""

    name: str
    description: str
    enabled_by_default: bool


class ResumeDecision(BaseModel):
    type: Literal["approve", "edit", "reject"]
    edited_action: dict[str, Any] | None = None


class ResumeRequest(BaseModel):
    search_space_id: int
    decisions: list[ResumeDecision]
    filesystem_mode: Literal["cloud", "desktop_local_folder"] = "cloud"
    client_platform: Literal["web", "desktop"] = "web"
    local_filesystem_mounts: list[LocalFilesystemMountPayload] | None = None


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
    created_by_user_id: str | None = None


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
