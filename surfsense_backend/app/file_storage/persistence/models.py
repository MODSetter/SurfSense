"""``document_files`` table: durable blobs associated with a document."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin

from .enums import DocumentFileKind


class DocumentFile(BaseModel, TimestampMixin):
    """One stored file for a document (its original upload, or a derived copy)."""

    __tablename__ = "document_files"

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    search_space_id = Column(
        "workspace_id",
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(
        SQLAlchemyEnum(
            DocumentFileKind,
            name="document_file_kind",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DocumentFileKind.ORIGINAL,
        server_default=DocumentFileKind.ORIGINAL.value,
        index=True,
    )

    # Where the bytes live: the backend that stored them and its object key.
    storage_backend = Column(String(32), nullable=False)
    storage_key = Column(String, nullable=False)

    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(String(64), nullable=True)

    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    document = relationship("Document", back_populates="files")
