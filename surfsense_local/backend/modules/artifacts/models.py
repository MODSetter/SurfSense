import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.chat.models import ChatThread
from modules.documents.models import Document
from modules.workspaces.models import Workspace
from shared.db import Base, text_enum


class ArtifactFileRole(enum.StrEnum):
    PRIMARY = "primary"
    PREVIEW = "preview"


class Artifact(Base):
    """Sidecar for an ARTIFACT document: bytes, format and provenance only.

    Per ADR-0003 the searchable body stays a Document, so this owns no title,
    path, markdown or indexing state.
    """

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("document_id"),
        CheckConstraint("generation > 0", name="generation_positive"),
        Index("artifacts_workspace", "workspace_id"),
        Index("artifacts_chat_thread", "chat_thread_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    # A deleted thread must not take the deliverable it produced with it.
    chat_thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="SET NULL")
    )
    # Not an enum: suffix inference may store kinds ArtifactFormat has no member for.
    format: Mapped[str]
    generation: Mapped[int] = mapped_column(default=1, server_default="1")
    created_by_tool_call_id: Mapped[str | None] = mapped_column(String(255))
    updated_by_tool_call_id: Mapped[str | None] = mapped_column(String(255))
    artifact_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="artifact")
    workspace: Mapped[Workspace] = relationship()
    chat_thread: Mapped[ChatThread | None] = relationship()
    files: Mapped[list["ArtifactFile"]] = relationship(
        back_populates="artifact", cascade="all, delete-orphan", passive_deletes=True
    )


class ArtifactFile(Base):
    """Immutable metadata for one durable blob under data/…/artifacts/{id}/."""

    __tablename__ = "artifact_files"
    __table_args__ = (
        UniqueConstraint("artifact_id", "role"),
        UniqueConstraint("storage_key"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_id: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    role: Mapped[ArtifactFileRole] = mapped_column(text_enum(ArtifactFileRole))
    storage_key: Mapped[str]
    original_filename: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    artifact: Mapped[Artifact] = relationship(back_populates="files")
