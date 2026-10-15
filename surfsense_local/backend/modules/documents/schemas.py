from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    ModelWrapValidatorHandler,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings.transcription_read import (
    TranscriptionRead,
    transcription_read,
)

DocumentTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class NoteCreate(BaseModel):
    """A document the user writes directly, with no file behind it."""

    model_config = ConfigDict(extra="forbid")

    title: DocumentTitle
    content: str
    document_metadata: dict[str, JsonValue] | None = None
    # The folder to file it in; the top of the Library when absent.
    folder_id: PositiveInt | None = None


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
    mime_type: str | None
    status: DocumentStatus
    error_message: str | None
    # None only for an unfiled artifact, or a source the SET NULL backstop
    # unfiled, which the tree shows at the top of the Library.
    folder_id: int | None
    created_at: datetime
    updated_at: datetime
    # Only for a recording: null for every other source.
    transcription: TranscriptionRead | None = None

    @model_validator(mode="wrap")
    @classmethod
    def _with_transcription(
        cls, value: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        # Read off the row and the job's progress file, never stored as a column.
        read = handler(value)
        if isinstance(value, Document):
            read.transcription = transcription_read(value)
        return read


class DocumentDetail(DocumentRead):
    """One document, including the text that was extracted from it."""

    content: str | None
    document_metadata: dict[str, JsonValue] | None


class ChunkRead(BaseModel):
    """One passage of a document, as the citation panel shows it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    position: int
    start_line: int | None
    end_line: int | None


class DocumentByChunkRead(BaseModel):
    """A document plus the window of chunks around a cited passage."""

    id: int
    title: str
    document_type: DocumentType
    workspace_id: int
    chunks: list[ChunkRead]
    total_chunks: int
    chunk_start_index: int


class DuplicateRead(BaseModel):
    """A file already held in the folder it was added to, byte for byte."""

    filename: str
    document_id: int
    folder_id: int | None


class RejectedUploadRead(BaseModel):
    """A file the ingestion pipeline cannot safely process."""

    filename: str
    reason: str


class UploadOutcome(BaseModel):
    """One upload can be a dropped folder, so each file gets its own verdict.

    Rejecting the whole batch over one duplicate would make the dropzone
    unusable; the client reports the split.
    """

    created: list[DocumentRead]
    duplicates: list[DuplicateRead]
    rejected: list[RejectedUploadRead]
