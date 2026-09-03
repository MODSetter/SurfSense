import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.workspaces.models import Workspace
from shared.db import Base


class DocumentType(enum.StrEnum):
    FILE = "FILE"
    NOTE = "NOTE"
    ARTIFACT = "ARTIFACT"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def _text_enum(members: type[enum.Enum]) -> Enum:
    """SQLite has no enum type, so store the values behind a CHECK constraint."""
    return Enum(
        members,
        native_enum=False,
        # Off by default since SQLAlchemy 1.4, which would leave the column a
        # bare VARCHAR that accepts anything.
        create_constraint=True,
        values_callable=lambda column: [member.value for member in column],
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("documents_workspace", "workspace_id"),
        Index(
            "documents_workspace_dedup_key",
            "workspace_id",
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
    document_type: Mapped[DocumentType] = mapped_column(_text_enum(DocumentType))
    status: Mapped[DocumentStatus] = mapped_column(
        _text_enum(DocumentStatus), default=DocumentStatus.PENDING
    )
    content: Mapped[str | None]
    content_hash: Mapped[str | None]
    dedup_key: Mapped[str | None]
    document_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="documents")
