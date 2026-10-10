"""A connected plugin as the screen sees it: never its credentials."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin, PluginTool


class ToolRead(BaseModel):
    name: str
    title: str | None
    description: str
    annotations: dict
    enabled: bool
    approval: str


class PluginRead(BaseModel):
    id: str
    name: str
    source: str
    publisher: str
    url: str
    hosts: list[str]
    enabled: bool
    connected_at: datetime
    tools: list[ToolRead]


def read_plugin(session: Session, plugin: InstalledPlugin) -> PluginRead:
    tools = session.scalars(
        select(PluginTool)
        .where(PluginTool.plugin_id == plugin.id)
        .order_by(PluginTool.position)
    )
    return PluginRead(
        id=plugin.id,
        name=plugin.entry.get("name", plugin.id),
        source=plugin.source,
        publisher=plugin.publisher,
        url=plugin.url,
        hosts=plugin.entry.get("hosts", []),
        enabled=plugin.enabled,
        connected_at=plugin.connected_at,
        tools=[
            ToolRead(
                name=tool.tool,
                title=tool.title,
                description=tool.description,
                annotations=tool.annotations,
                enabled=tool.enabled,
                approval=tool.approval,
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
    return [read_plugin(session, plugin) for plugin in plugins]
