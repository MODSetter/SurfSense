from pydantic import BaseModel, Field, field_validator

from app.db import DocumentType


class ConnectorDocument(BaseModel):
    """Canonical data transfer object produced by connector adapters and consumed by the indexing pipeline."""

    title: str
    source_markdown: str
    unique_id: str
    document_type: DocumentType
    search_space_id: int = Field(gt=0)
    should_summarize: bool = True
    should_use_code_chunker: bool = False
    fallback_summary: str | None = None
    metadata: dict = {}
    connector_id: int | None = None
    created_by_id: str

    @field_validator("title", "source_markdown", "unique_id", "created_by_id")
    @classmethod
    def not_empty(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace")
        return v
