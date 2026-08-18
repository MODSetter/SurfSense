"""Artifact sidecar and immutable artifact-file models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin

from .enums import ArtifactFileRole


class Artifact(BaseModel, TimestampMixin):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_artifacts_document_id"),
        CheckConstraint("generation > 0", name="ck_artifacts_generation_positive"),
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    format = Column(String, nullable=False)
    generation = Column(Integer, nullable=False, default=1, server_default="1")

    created_by_tool_call_id = Column(String(255), nullable=True)
    updated_by_tool_call_id = Column(String(255), nullable=True)
    artifact_metadata = Column("metadata", JSONB, nullable=True)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )

    document = relationship("Document", back_populates="artifact")
    workspace = relationship("Workspace")
    thread = relationship("NewChatThread")
    created_by = relationship("User")
    files = relationship(
        "ArtifactFile",
        back_populates="artifact",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ArtifactFile(BaseModel, TimestampMixin):
    """Immutable metadata for one durable artifact blob."""

    __tablename__ = "artifact_files"
    __table_args__ = (
        UniqueConstraint("artifact_id", "role", name="uq_artifact_files_artifact_role"),
        UniqueConstraint("storage_key", name="uq_artifact_files_storage_key"),
        CheckConstraint("size_bytes > 0", name="ck_artifact_files_size_positive"),
    )

    artifact_id = Column(
        Integer,
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        SQLAlchemyEnum(
            ArtifactFileRole,
            name="artifact_file_role",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    storage_backend = Column(String(32), nullable=False)
    storage_key = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)

    artifact = relationship("Artifact", back_populates="files")
