"""``podcasts`` table: a generated podcast, its brief, transcript, and state."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin

from .enums import PodcastStatus


class Podcast(BaseModel, TimestampMixin):
    """A podcast across its whole lifecycle: brief, transcript, audio, status.

    ``spec`` (the reviewable brief) and ``podcast_transcript`` are JSONB so the
    flexible Pydantic shapes can evolve without migrations. ``spec_version``
    backs optimistic concurrency on brief edits. Rendered audio lives in the
    object store, addressed by ``storage_backend`` + ``storage_key`` rather than
    a raw path.
    """

    __tablename__ = "podcasts"

    title = Column(String(500), nullable=False)

    status = Column(
        SQLAlchemyEnum(
            PodcastStatus,
            name="podcast_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PodcastStatus.PENDING,
        server_default=PodcastStatus.PENDING.value,
        index=True,
    )

    # The source material the episode is generated from. Persisted because
    # drafting happens after the brief gate, long after creation.
    source_content = Column(Text, nullable=True)

    # The reviewable brief (PodcastSpec); null until the brief gate is reached.
    spec = Column(JSONB, nullable=True)
    # Bumped on every spec edit; guards concurrent edits at the brief gate.
    spec_version = Column(Integer, nullable=False, default=1, server_default="1")

    # The drafted dialogue (Transcript); null until drafting completes.
    podcast_transcript = Column(JSONB, nullable=True)

    # Where the rendered audio lives in the object store; null until READY.
    storage_backend = Column(String(32), nullable=True)
    storage_key = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Human-readable reason when status is FAILED.
    error = Column(Text, nullable=True)

    # Legacy local audio path; retained for back-compat until cutover.
    file_location = Column(Text, nullable=True)

    search_space_id = Column(
        "workspace_id",
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_space = relationship("SearchSpace", back_populates="podcasts")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")
