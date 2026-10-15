import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.workspaces.models import Workspace
from shared.db import Base, text_enum

if TYPE_CHECKING:
    from modules.artifacts.models import Artifact
    from modules.chunks.models import Chunk


class DocumentType(enum.StrEnum):
    FILE = "FILE"
    NOTE = "NOTE"
    ARTIFACT = "ARTIFACT"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("documents_workspace", "workspace_id"),
        Index("documents_folder", "folder_id"),
        # Per folder: a copied folder keeps a file that already sits elsewhere.
        Index(
            "documents_folder_dedup_key",
            "workspace_id",
            "folder_id",
            "dedup_key",
            unique=True,
            sqlite_where=text("dedup_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    title: Mapped[str]
    document_type: Mapped[DocumentType] = mapped_column(text_enum(DocumentType))
    status: Mapped[DocumentStatus] = mapped_column(
        text_enum(DocumentStatus), default=DocumentStatus.PENDING
    )
    # Set when status is failed, so the documents view can show the reason.
    error_message: Mapped[str | None]
    content: Mapped[str | None]
    content_hash: Mapped[str | None]
    dedup_key: Mapped[str | None]
    document_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Every FILE and NOTE is filed; None is an unfiled artifact, or the SET NULL
    # backstop, which scopes and the tree still treat as the Library's top.
    # ON DELETE SET NULL is declared by 0025 inline, where SQLAlchemy's SQLite
    # reflection cannot read it, so declaring it here too would read as drift.
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))
    # The index its chunks were embedded into; what a re-embed has not reached.
    embedding_index_id: Mapped[int | None] = mapped_column(
        ForeignKey("embedding_indexes.id")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    artifact: Mapped["Artifact | None"] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def mime_type(self) -> str | None:
        if self.document_type is not DocumentType.FILE:
            return None
        mime_type = (self.document_metadata or {}).get("mime_type")
        return mime_type if isinstance(mime_type, str) else None
