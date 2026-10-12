"""Whether a plugin's server signs in with OAuth, and the authorization server's hosts.

Read before the sign-in starts, so the user is asked about those hosts before any request
reaches them. The SDK discovers again during the sign-in itself; its own requests go
through the same consented client.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from mcp.client.auth.utils import (
    build_protected_resource_metadata_discovery_urls,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    handle_protected_resource_response,
)

from modules.plugins.remote.sign_in.oauth.consented_client import consented_client

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "SurfSense", "version": "0"},
    },
}
_ACCEPT = {"accept": "application/json, text/event-stream"}


@dataclass(frozen=True)
class OAuthDiscovery:
    # Empty when the server is its own authorization server, as 2025-03-26 servers are.
    authorization_server_hosts: list[str]


async def discover_oauth(url: str, allowed_hosts: set[str]) -> OAuthDiscovery | None:
    """None when the server's refusal does not ask for OAuth, as a server wanting a key's does."""
    async with consented_client(allowed_hosts) as http:
        probe = await http.post(url, json=_INITIALIZE, headers=_ACCEPT)
        if probe.status_code != 401:
            return None
        named = extract_resource_metadata_from_www_auth(probe)
        for candidate in build_protected_resource_metadata_discovery_urls(named, url):
            found = await handle_protected_resource_response(
                await http.send(create_oauth_metadata_request(candidate))
            )
            if found is not None:
                server = str(found.authorization_servers[0])
                return OAuthDiscovery([urlsplit(server).hostname or ""])
        origin = urlsplit(url)._replace(path="", query="", fragment="").geturl()
        legacy = await http.send(
            create_oauth_metadata_request(
                f"{origin}/.well-known/oauth-authorization-server"
            )
        )
        return OAuthDiscovery([]) if legacy.status_code == 200 else None
