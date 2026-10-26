"""A connected plugin's headers, replaced in place so the user's choices per tool stay."""

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin, PluginSource
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.headers.headers_credential import (
    headers_auth,
    write_headers,
)


def replace_headers(
    session: Session,
    plugin: InstalledPlugin,
    headers: list[SignInHeader],
    tools: list[SourceTool],
) -> None:
    """Only headers the server just accepted are saved, with what it listed as the check."""
    write_headers(plugin, headers)
    plugin.disconnected_at = None
    # A registry plugin keeps its reviewed entry, which names and words its headers.
    if plugin.source != PluginSource.REGISTRY:
        plugin.entry = {**plugin.entry, "auth": headers_auth(headers)}
    record_check(session, plugin, tools)
