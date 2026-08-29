"""A git destination this workspace pushes HEAD to."""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db import BaseModel, TimestampMixin


class WorkspaceGitRemotes(BaseModel, TimestampMixin):
    """A push target this workspace exports HEAD to. v1: unique on workspace_id.

    ponytail: that unique is the one-remote ceiling. Drop it to allow many;
    ``WorkspaceRemotes.add`` already treats remotes as a collection.
    """

    __tablename__ = "workspace_git_remotes"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_workspace_git_remotes_workspace"),
    )

    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace = relationship("Workspace")

    provider = Column(String(16), nullable=False)
    url = Column(String(512), nullable=False)
    branch = Column(String(255), nullable=False, default="main")
    installation_id = Column(String(64), nullable=True)
    token = Column(Text, nullable=True)
    last_pushed_revision = Column(String(64), nullable=True)
    last_pushed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_push_error = Column(Text, nullable=True)
