"""
Pydantic schemas for chat comments and mentions.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Request Schemas
# =============================================================================


class CommentCreateRequest(BaseModel):
    """Schema for creating a comment or reply."""

    content: str = Field(..., min_length=1, max_length=5000)


class CommentUpdateRequest(BaseModel):
    """Schema for updating a comment."""

    content: str = Field(..., min_length=1, max_length=5000)


# =============================================================================
# Author Schema
# =============================================================================


class AuthorResponse(BaseModel):
    """Author information for comments."""

    id: UUID
    display_name: str | None = None
    avatar_url: str | None = None
    email: str

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Comment Schemas
# =============================================================================


class CommentReplyResponse(BaseModel):
    """Schema for a comment reply (no nested replies)."""

    id: int
    content: str
    content_rendered: str
    author: AuthorResponse | None = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    can_edit: bool = False
    can_delete: bool = False

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Schema for a top-level comment with replies."""

    id: int
    message_id: int
    content: str
    content_rendered: str
    author: AuthorResponse | None = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    can_edit: bool = False
    can_delete: bool = False
    reply_count: int
    replies: list[CommentReplyResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    """Response for listing comments on a message."""

    comments: list[CommentResponse]
    total_count: int


# =============================================================================
# Mention Schemas
# =============================================================================


class MentionContextResponse(BaseModel):
    """Context information for where a mention occurred."""

    thread_id: int
    thread_title: str
    message_id: int
    search_space_id: int
    search_space_name: str


class MentionCommentResponse(BaseModel):
    """Abbreviated comment info for mention display."""

    id: int
    content_preview: str
    author: AuthorResponse | None = None
    created_at: datetime


class MentionResponse(BaseModel):
    """Schema for a mention notification."""

    id: int
    created_at: datetime
    comment: MentionCommentResponse
    context: MentionContextResponse

    model_config = ConfigDict(from_attributes=True)


class MentionListResponse(BaseModel):
    """Response for listing user's mentions."""

    mentions: list[MentionResponse]
    total_count: int
