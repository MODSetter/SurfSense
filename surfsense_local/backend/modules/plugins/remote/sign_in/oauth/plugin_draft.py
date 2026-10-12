"""What a plugin's row will hold once its sign-in succeeds; nothing is stored before."""

from dataclasses import dataclass, replace
from typing import Any

from mcp.shared.auth import OAuthClientInformationFull

from modules.plugins.installed.models import PluginSource


@dataclass(frozen=True)
class PluginDraft:
    plugin_id: str
    name: str
    url: str
    source: PluginSource
    publisher: str
    # As stored on the row; its `hosts` gain the authorization server's once discovered.
    entry: dict[str, Any]
    scopes: list[str] | None = None
    # SurfSense's app as registered in advance with a provider; never with a secret.
    client_id: str | None = None
    # The client an earlier sign-in registered, reused when signing in again.
    previous_client: OAuthClientInformationFull | None = None
    # Signing in again on a connected plugin, whose tool settings stay.
    existing: bool = False

    def with_hosts(self, hosts: list[str]) -> "PluginDraft":
        merged = list(dict.fromkeys([*self.entry.get("hosts", []), *hosts]))
        return replace(self, entry={**self.entry, "hosts": merged})
