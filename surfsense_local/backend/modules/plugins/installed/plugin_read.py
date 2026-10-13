"""A connected plugin as the screen sees it: never its credentials."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin, PluginTool
from modules.plugins.lists.registry.delisted import delisted_reason, delisted_reasons


class ToolRead(BaseModel):
    name: str
    title: str | None
    description: str
    annotations: dict
    enabled: bool
    approval: str
    # `added` or `changed` while it waits for the user to allow it; None otherwise.
    change: str | None


class PluginRead(BaseModel):
    id: str
    name: str
    source: str
    url: str
    hosts: list[str]
    # How it signs in: `none`, `token`, `license` or `oauth`.
    auth_type: str
    enabled: bool
    # Disconnected by the user: kept with its tool settings, signed out, never offered.
    disconnected: bool
    connected_at: datetime
    checked_at: datetime | None
    # `unreachable` or `sign_in` when the last check failed; None when it answered.
    check_failure: str | None
    # Why the registry delisted it; its tools are no longer offered. None otherwise.
    removed_reason: str | None = None
    tools: list[ToolRead]


def read_plugin(
    session: Session,
    plugin: InstalledPlugin,
    delisted: dict[str, str] | None = None,
) -> PluginRead:
    tools = session.scalars(
        select(PluginTool)
        .where(PluginTool.plugin_id == plugin.id)
        .order_by(PluginTool.position)
    )
    return PluginRead(
        id=plugin.id,
        name=plugin.entry.get("name", plugin.id),
        source=plugin.source,
        url=plugin.url,
        hosts=plugin.entry.get("hosts", []),
        auth_type=plugin.credential_kind or "none",
        enabled=plugin.enabled,
        disconnected=plugin.disconnected_at is not None,
        connected_at=plugin.connected_at,
        checked_at=plugin.checked_at,
        check_failure=plugin.check_failure,
        removed_reason=delisted_reason(
            plugin, delisted_reasons() if delisted is None else delisted
        ),
        tools=[
            ToolRead(
                name=tool.tool,
                title=tool.title,
                description=tool.description,
                annotations=tool.annotations,
                enabled=tool.enabled,
                approval=tool.approval,
                change=tool.change,
            )
            for tool in tools
        ],
    )


def read_plugins(session: Session) -> list[PluginRead]:
    plugins = session.scalars(
        select(InstalledPlugin).order_by(
            InstalledPlugin.connected_at, InstalledPlugin.id
        )
    )
    delisted = delisted_reasons()
    return [read_plugin(session, plugin, delisted) for plugin in plugins]
