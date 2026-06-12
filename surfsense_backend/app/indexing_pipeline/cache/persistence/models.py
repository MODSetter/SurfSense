"""``index_cache_embedding_sets``: one reusable chunk+embedding set per markdown."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.db import BaseModel, TimestampMixin


class CachedEmbeddingSet(BaseModel, TimestampMixin):
    __tablename__ = "index_cache_embedding_sets"

    # Key: markdown text + the recipe that turned it into vectors.
    markdown_sha256 = Column(String(64), nullable=False)
    embedding_model = Column(String(255), nullable=False)
    embedding_dim = Column(Integer, nullable=False)
    chunker_kind = Column(String(8), nullable=False)
    chunker_version = Column(Integer, nullable=False)

    # Where the embedding blob lives (kept out of the row to stay small).
    storage_backend = Column(String(32), nullable=False)
    storage_key = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0, server_default="0")

    # Drives eviction (popularity + recency).
    times_reused = Column(BigInteger, nullable=False, default=0, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "markdown_sha256",
            "embedding_model",
            "chunker_kind",
            "chunker_version",
            name="uq_index_cache_embedding_sets_key",
        ),
        Index("ix_index_cache_embedding_sets_last_used_at", "last_used_at"),
    )
