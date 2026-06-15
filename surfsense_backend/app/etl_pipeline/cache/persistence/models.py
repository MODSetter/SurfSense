"""``etl_cache_parses``: one reusable parser result per (bytes + recipe)."""

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


class CachedParse(BaseModel, TimestampMixin):
    __tablename__ = "etl_cache_parses"

    # Key: raw bytes + the recipe that produced the markdown.
    source_sha256 = Column(String(64), nullable=False)
    etl_service = Column(String(32), nullable=False)
    mode = Column(String(16), nullable=False)
    parser_version = Column(Integer, nullable=False)

    # Where the markdown blob lives (kept out of the row to stay small).
    storage_backend = Column(String(32), nullable=False)
    storage_key = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)

    # Payload needed to rebuild the EtlResult on a hit.
    content_type = Column(String(32), nullable=False)
    actual_pages = Column(Integer, nullable=False, default=0, server_default="0")

    # Drives eviction (popularity + recency).
    times_reused = Column(BigInteger, nullable=False, default=0, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_sha256",
            "etl_service",
            "mode",
            "parser_version",
            name="uq_etl_cache_parses_key",
        ),
        Index("ix_etl_cache_parses_last_used_at", "last_used_at"),
    )
