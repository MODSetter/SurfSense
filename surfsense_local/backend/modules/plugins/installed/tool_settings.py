"""The user's switch and approval setting on one tool of a connected plugin."""

from sqlalchemy.orm import Session

from modules.plugins.installed.models import PluginTool, ToolApproval


def set_tool(
    session: Session,
    plugin_id: str,
    tool: str,
    *,
    enabled: bool | None,
    approval: ToolApproval | None,
) -> PluginTool | None:
    """None when the plugin has no such tool."""
    row = session.get(PluginTool, (plugin_id, tool))
    if row is None:
        return None
    if enabled is not None:
        row.enabled = enabled
        if enabled:
            # Allowed as it now reads, so it is no longer news.
            row.change = None
    if approval is not None:
        row.approval = approval
    session.flush()
    return row
