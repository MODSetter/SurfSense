from datetime import datetime
from typing import TypeVar

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
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


class DocumentWithChunksRead(DocumentRead):
    chunks: list[ChunkRead] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
