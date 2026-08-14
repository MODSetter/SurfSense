"""``podcast_runs`` table: a generated podcast, its brief, transcript, state."""

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
    """A podcast run: brief, transcript, lifecycle state, and its Artifact link.

    ``spec`` (the reviewable brief) and ``podcast_transcript`` are JSONB so the
    flexible Pydantic shapes can evolve without migrations. ``spec_version``
    backs optimistic concurrency on brief edits. The delivered audio and
    markdown live in the Artifact referenced by ``artifact_id``.
    """

    __tablename__ = "podcast_runs"

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

    duration_seconds = Column(Integer, nullable=True)

    # Human-readable reason when status is FAILED.
    error = Column(Text, nullable=True)

    # The delivered Artifact; NULL until READY. The Artifact owns the audio.
    artifact_id = Column(
        Integer,
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace", back_populates="podcasts")

    thread_id = Column(
        Integer,
        ForeignKey("new_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread = relationship("NewChatThread")
