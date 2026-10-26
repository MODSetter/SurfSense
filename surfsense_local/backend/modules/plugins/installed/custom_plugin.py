"""A remote server the user adds by URL: in the user's app only, in neither list."""

import re
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import (
    InstalledPlugin,
    PluginKind,
    PluginSource,
)
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.lists.first_party.first_party_list import first_party_entries
from modules.plugins.lists.registry.listed_ids import registry_ids
from modules.plugins.remote.sign_in.headers.header_rules import SignInHeader
from modules.plugins.remote.sign_in.headers.headers_credential import (
    headers_auth,
    write_headers,
)

# The agent's own tools are an MCP server by this name; a plugin under it would replace them.
RESERVED_IDS = {"surfsense"}


def custom_plugin_id(name: str) -> str:
    """The name as an id: lowercase words joined by hyphens, as list entries' ids are."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "plugin"
    # Listed plugins keep their ids, so each can still be connected under its own.
    taken = (
        RESERVED_IDS | {entry.id for entry in first_party_entries()} | registry_ids()
    )
    return f"{slug}-plugin" if slug in taken else slug


def connected_name(session: Session, url: str) -> str | None:
    """The name a plugin at `url` is connected as, or None."""
    plugin = session.scalars(
        select(InstalledPlugin).where(InstalledPlugin.url == url)
    ).first()
    return plugin.entry.get("name", plugin.id) if plugin else None


def url_host(url: str) -> str:
    return urlsplit(url).hostname or ""


def store_custom_plugin(
    session: Session,
    plugin_id: str,
    name: str,
    url: str,
    headers: list[SignInHeader] | None,
    tools: list[SourceTool],
) -> InstalledPlugin:
    plugin = InstalledPlugin(
        id=plugin_id,
        kind=PluginKind.REMOTE,
        source=PluginSource.CUSTOM,
        url=url,
        entry={
            "name": name,
            "hosts": [url_host(url)],
            "auth": headers_auth(headers) if headers else {"type": "none"},
        },
    )
    if headers:
        write_headers(plugin, headers)
    session.add(plugin)
    session.flush()
    record_check(session, plugin, tools)
    return plugin
