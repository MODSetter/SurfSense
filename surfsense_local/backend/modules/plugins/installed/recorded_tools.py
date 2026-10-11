"""Record what a connected plugin's source lists, applying the rule for tools added later.

At connect every tool starts on: the user reviewed the plugin then. After that a server
can change any day, so a new tool starts off, a tool whose description changes or whose
annotations become less safe is switched off, and a removed tool disappears.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.less_safe import became_less_safe
from modules.plugins.installed.models import InstalledPlugin, PluginTool, ToolChange


def record_tools(
    session: Session, plugin: InstalledPlugin, listed: list[SourceTool]
) -> None:
    known = {
        row.tool: row
        for row in session.scalars(
            select(PluginTool).where(PluginTool.plugin_id == plugin.id)
        )
    }
    first_listing = not known
    for position, tool in enumerate(listed):
        row = known.pop(tool.name, None)
        if row is None:
            row = PluginTool(plugin_id=plugin.id, tool=tool.name, enabled=first_listing)
            if not first_listing:
                row.change = ToolChange.ADDED
            session.add(row)
        elif tool.description != row.description or became_less_safe(
            row.annotations, tool.annotations
        ):
            row.enabled = False
            row.change = ToolChange.CHANGED
        row.position = position
        row.title = tool.title
        row.description = tool.description
        row.input_schema = tool.input_schema
        row.annotations = tool.annotations
    for removed in known.values():
        session.delete(removed)
    session.flush()
