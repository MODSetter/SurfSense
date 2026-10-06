import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class SourceRootKind(enum.StrEnum):
    # The Library: folders the user makes in the app, bytes in the data directory.
    MANAGED = "managed"
    # A folder on disk, indexed in place. Not built yet.
    LINKED = "linked"


class SourceRootState(enum.StrEnum):
    # Every state linked roots will need, so adding one never rebuilds the
    # table: a rebuild cascades into folders and unfiles every document.
    READY = "ready"
    SCANNING = "scanning"
    UNAVAILABLE = "unavailable"
    PAUSED = "paused"
    UNLINKING = "unlinking"


class SourceRoot(Base):
    """Where a tree of folders comes from; each workspace has one managed Library."""

    __tablename__ = "source_roots"
    __table_args__ = (
        Index("source_roots_workspace_name", "workspace_id", "name_key", unique=True),
        Index(
            "source_roots_one_managed",
            "workspace_id",
            unique=True,
            sqlite_where=text("kind = 'managed'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    kind: Mapped[SourceRootKind] = mapped_column(text_enum(SourceRootKind))
    name: Mapped[str]
    name_key: Mapped[str]
    # The resolved absolute path of a linked root; None for the Library.
    disk_path: Mapped[str | None]
    state: Mapped[SourceRootState] = mapped_column(
        text_enum(SourceRootState), default=SourceRootState.READY
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
