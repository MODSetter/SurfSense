from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from modules.documents.models import DocumentStatus, DocumentType

DocumentTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class NoteCreate(BaseModel):
    """A document the user writes directly, with no file behind it."""

    title: DocumentTitle
    content: str


class DocumentUpdate(BaseModel):
    """Fields a client may change. Unset fields are left alone."""

    title: DocumentTitle | None = None
    content: str | None = None


class DocumentRead(BaseModel):
    """A row of the documents table, without the body it would bloat every poll with."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_type: DocumentType
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentRead):
    """One document, including the text that was extracted from it."""

    content: str | None
