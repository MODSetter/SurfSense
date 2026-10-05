import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class FolderState(enum.StrEnum):
    READY = "ready"
    # A cloud directory on a linked root that was never downloaded.
    PLACEHOLDER = "placeholder"
    TRASHED = "trashed"
    # Its documents are being removed; already out of every scope and the tree.
    DELETING = "deleting"


class TrashKind(enum.StrEnum):
    FOLDER = "folder"
    DOCUMENTS = "documents"


class Folder(Base):
    """A folder in a source root. The root's own folder has no parent and is depth 0."""

    __tablename__ = "folders"
    __table_args__ = (
        Index("folders_root", "root_id"),
        Index("folders_workspace", "workspace_id"),
        # Live siblings only: a trashed folder must not block its name.
        Index(
            "folders_sibling_name",
            "parent_id",
            "name_key",
            unique=True,
            sqlite_where=text(
                "parent_id IS NOT NULL AND state IN ('ready', 'placeholder')"
            ),
        ),
        Index(
            "folders_one_root_folder",
            "root_id",
            unique=True,
            sqlite_where=text("parent_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    root_id: Mapped[int] = mapped_column(
        ForeignKey("source_roots.id", ondelete="CASCADE")
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE")
    )
    name: Mapped[str]
    name_key: Mapped[str]
    # The name on disk under a linked root, where `name` may be cleaned for display.
    disk_name: Mapped[str | None]
    # One of the product's job roles (evidence, target, playbook, library).
    role: Mapped[str | None]
    state: Mapped[FolderState] = mapped_column(
        text_enum(FolderState), default=FolderState.READY
    )
    trash_kind: Mapped[TrashKind | None] = mapped_column(text_enum(TrashKind))
    trashed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
