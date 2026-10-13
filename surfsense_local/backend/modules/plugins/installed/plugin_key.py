"""A connected plugin's key, replaced in place so the user's choices per tool stay."""

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.plugin_check import record_check


def replace_key(
    session: Session, plugin: InstalledPlugin, token: str, tools: list[SourceTool]
) -> None:
    """Only a key the server just accepted is saved, with what it listed as the check."""
    plugin.credential_kind = "token"
    plugin.credential = token
    plugin.disconnected_at = None
    plugin.entry = {**plugin.entry, "auth": {"type": "token"}}
    record_check(session, plugin, tools)
