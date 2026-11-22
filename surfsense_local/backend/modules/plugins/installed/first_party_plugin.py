"""Connecting one of SurfSense's own plugins from the first-party list."""

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin, PluginKind, PluginSource
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.lists.list_entry import ListEntry
from modules.plugins.remote.mcp_client.server_error import ServerError


def store_first_party_plugin(
    session: Session, entry: ListEntry, listed: list[SourceTool] | ServerError
) -> InstalledPlugin:
    """Kept even when the server refused the license: the plugin's status then says why."""
    plugin = InstalledPlugin(
        id=entry.id,
        kind=PluginKind.REMOTE,
        source=PluginSource.FIRST_PARTY,
        url=entry.url,
        entry=entry.model_dump(exclude_none=True),
        credential_kind=entry.auth.type if entry.auth.type != "none" else None,
    )
    session.add(plugin)
    session.flush()
    record_check(session, plugin, listed)
    return plugin
