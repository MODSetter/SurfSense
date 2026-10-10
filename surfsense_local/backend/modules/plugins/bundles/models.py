import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum


class PluginRunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PluginRun(Base):
    """One run of a plugin's action in a workspace, and how it ended.

    What the run produced is not here: the plugin wrote it through the API
    while it ran.
    """

    __tablename__ = "plugin_runs"
    __table_args__ = (Index("plugin_runs_workspace", "workspace_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    plugin_id: Mapped[str]
    # The installed version the run uses, so its folder is known to be in use.
    version: Mapped[str]
    action: Mapped[str]
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[PluginRunStatus] = mapped_column(
        text_enum(PluginRunStatus), default=PluginRunStatus.QUEUED
    )
    # Set when status is failed: `exit <code>`, as the protocol names it.
    error: Mapped[str | None]
    # The last of what the plugin printed, which is where it explains a failure.
    log_tail: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
