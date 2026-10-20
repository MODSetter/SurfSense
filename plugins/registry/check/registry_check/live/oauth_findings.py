"""Whether SurfSense can sign in to an OAuth server, found the way the app finds it."""

from typing import Any
from urllib.parse import urlsplit

import httpx2
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    should_use_client_metadata_url,
)
from mcp.shared.auth import OAuthMetadata

from registry_check.live.failure_reason import failure_reason
from registry_check.live.findings import Findings
from registry_check.live.web import web_client

# The packaged app's client metadata document, which a server may accept instead of DCR.
SURFSENSE_CLIENT = "https://plugins.surfsense.com/oauth/client.json"
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


async def oauth_findings(entry: dict[str, Any]) -> Findings:
    found = Findings()
    url = entry["url"]
    try:
        issuer, metadata = await discovered(url)
    except httpx2.HTTPError as error:
        found.problems.append(
            f"auth: sign-in could not be checked: {failure_reason(error)}"
        )
        return found
    if metadata is None:
        found.problems.append(
            "auth: oauth, but the server names no authorization server "
            "(RFC 9728 protected resource metadata, or RFC 8414 on its origin)"
        )
        return found
    endpoints = sign_in_endpoints(url, issuer, metadata)
    listed = set(entry.get("hosts") or [])
    reached = sorted({urlsplit(e).hostname or "" for e in endpoints} - listed)
    for host in reached:
        # The app asks the user about every host first, and refuses one not listed.
        found.problems.append(f"hosts: sign-in reaches {host}, which hosts leaves out")
    auth = entry.get("auth") or {}
    # A `user_client` entry's users bring an app the provider registered in advance.
    registered = auth.get("client_id") or auth.get("user_client")
    if not (
        registered
        or metadata.registration_endpoint
        or should_use_client_metadata_url(metadata, SURFSENSE_CLIENT)
    ):
        found.problems.append(
            "auth: the authorization server takes neither a client metadata document "
            "nor dynamic registration, and the entry has no client_id"
        )
    return found


def sign_in_endpoints(
    url: str, issuer: str | None, metadata: OAuthMetadata
) -> list[str]:
    """Every address the app's sign-in reaches, so each host is listed and agreed to."""
    return [
        issuer or url,
        str(metadata.authorization_endpoint),
        str(metadata.token_endpoint),
        *(
            [str(metadata.registration_endpoint)]
            if metadata.registration_endpoint
            else []
        ),
    ]


async def discovered(url: str) -> tuple[str | None, OAuthMetadata | None]:
    """The authorization server and its metadata, as the app's sign-in finds them."""
    async with web_client() as http:
        probe = await http.post(url, json=_INITIALIZE, headers=_ACCEPT)
        # RFC 9728 first; a 2025-03-26 server is its own authorization server.
        issuer = None
        named = extract_resource_metadata_from_www_auth(probe)
        for candidate in build_protected_resource_metadata_discovery_urls(named, url):
            resource = await handle_protected_resource_response(
                await http.send(create_oauth_metadata_request(candidate))
            )
            if resource is not None and resource.authorization_servers:
                issuer = str(resource.authorization_servers[0])
                break
        return issuer, await _issuer_metadata(http, issuer, url)


async def _issuer_metadata(http, issuer: str | None, url: str) -> OAuthMetadata | None:
    for candidate in build_oauth_authorization_server_metadata_discovery_urls(
        issuer, url
    ):
        keep_looking, metadata = await handle_auth_metadata_response(
            await http.send(create_oauth_metadata_request(candidate))
        )
        if metadata is not None or not keep_looking:
            return metadata
    return None
