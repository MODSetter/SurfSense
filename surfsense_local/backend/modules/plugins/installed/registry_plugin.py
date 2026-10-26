"""Connecting a verified or community plugin from the registry."""

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin, PluginKind, PluginSource
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.lists.registry.registry_entry import RegistryEntry
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.headers.headers_credential import write_headers


def store_registry_plugin(
    session: Session,
    entry: RegistryEntry,
    token: str | None,
    tools: list[SourceTool],
    headers: list[SignInHeader] | None = None,
) -> InstalledPlugin:
    plugin = InstalledPlugin(
        id=entry.id,
        kind=PluginKind.REMOTE,
        source=PluginSource.REGISTRY,
        url=entry.url,
        entry=entry.model_dump(exclude_none=True),
    )
    if token:
        plugin.credential_kind = "token"
        plugin.credential = token
    if headers:
        write_headers(plugin, headers)
    session.add(plugin)
    session.flush()
    record_check(session, plugin, tools)
    return plugin
