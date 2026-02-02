from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db import DocumentType

from .chunks import ChunkRead

T = TypeVar("T")


class ExtensionDocumentMetadata(BaseModel):
    BrowsingSessionId: str
    VisitedWebPageURL: str
    VisitedWebPageTitle: str
    VisitedWebPageDateWithTimeInISOString: str
    VisitedWebPageReffererURL: str
    VisitedWebPageVisitDurationInMilliseconds: str


class ExtensionDocumentContent(BaseModel):
    metadata: ExtensionDocumentMetadata
    pageContent: str  # noqa: N815


class DocumentBase(BaseModel):
    document_type: DocumentType
    content: (
        list[ExtensionDocumentContent] | list[str] | str
    )  # Updated to allow string content
    search_space_id: int


class DocumentsCreate(DocumentBase):
    pass


class DocumentUpdate(DocumentBase):
    pass


class DocumentRead(BaseModel):
    id: int
    title: str
    document_type: DocumentType
    document_metadata: dict
    content: str  # Changed to string to match frontend
    content_hash: str
    unique_identifier_hash: str | None
    created_at: datetime
    updated_at: datetime | None
    search_space_id: int
    created_by_id: UUID | None = None  # User who created/uploaded this document

    model_config = ConfigDict(from_attributes=True)


class DocumentWithChunksRead(DocumentRead):
    chunks: list[ChunkRead] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class DocumentTitleRead(BaseModel):
    """Lightweight document response for mention picker - only essential fields."""

    id: int
    title: str
    document_type: DocumentType

    model_config = ConfigDict(from_attributes=True)


class DocumentTitleSearchResponse(BaseModel):
    """Response for document title search - optimized for typeahead."""

    items: list[DocumentTitleRead]
    has_more: bool
