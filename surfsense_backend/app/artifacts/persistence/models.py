"""Dedicated artifact, artifact-file, and artifact-chunk models."""

from __future__ import annotations

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import relationship

from app.config import config
from app.db import BaseModel, TimestampMixin

from .enums import ArtifactFileRole


class Artifact(BaseModel, TimestampMixin):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "path", name="uq_artifacts_workspace_path"
        ),
        CheckConstraint("generation > 0", name="ck_artifacts_generation_positive"),
        CheckConstraint(
            "indexed_generation IS NULL OR "
            "(indexed_generation > 0 AND indexed_generation <= generation)",
            name="ck_artifacts_indexed_generation_valid",
        ),
        Index(
            "artifacts_vector_index",
            "summary_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"summary_embedding": "vector_cosine_ops"},
        ),
        Index(
            "artifacts_search_index",
            text("to_tsvector('english', search_content)"),
            postgresql_using="gin",
        ),
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

    title = Column(String, nullable=False)
    format = Column(String, nullable=False)
    search_content = Column(Text, nullable=False)
    path = Column(String, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    summary_embedding = Column(Vector(config.embedding_model_instance.dimension))

    generation = Column(Integer, nullable=False, default=1, server_default="1")
    indexed_generation = Column(Integer, nullable=True)
    indexing_status = Column(
        String(32), nullable=False, default="pending", server_default="pending", index=True
    )
    indexing_error = Column(Text, nullable=True)

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

    workspace = relationship("Workspace")
    thread = relationship("NewChatThread")
    created_by = relationship("User")
    files = relationship(
        "ArtifactFile",
        back_populates="artifact",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks = relationship(
        "ArtifactChunk",
        back_populates="artifact",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArtifactChunk.position",
    )


class ArtifactFile(BaseModel, TimestampMixin):
    """Immutable metadata for one durable artifact blob."""

    __tablename__ = "artifact_files"
    __table_args__ = (
        UniqueConstraint(
            "artifact_id", "role", name="uq_artifact_files_artifact_role"
        ),
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


class ArtifactChunk(BaseModel, TimestampMixin):
    __tablename__ = "artifact_chunks"
    __table_args__ = (
        CheckConstraint(
            "position >= 0", name="ck_artifact_chunks_position_nonnegative"
        ),
        CheckConstraint(
            "(start_line IS NULL AND end_line IS NULL) OR "
            "(start_line IS NOT NULL AND end_line IS NOT NULL "
            "AND start_line > 0 AND end_line >= start_line)",
            name="ck_artifact_chunks_line_range",
        ),
        Index(
            "artifact_chunks_vector_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "artifact_chunks_search_index",
            text("to_tsvector('english', content)"),
            postgresql_using="gin",
        ),
    )

    artifact_id = Column(
        Integer,
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(config.embedding_model_instance.dimension))
    position = Column(Integer, nullable=False, default=0, server_default="0")
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)

    artifact = relationship("Artifact", back_populates="chunks")
