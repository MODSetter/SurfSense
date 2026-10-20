"""Whether a provider offers dynamic registration at all, read after a registration failed.

Its host is allowed by then, so this tells "registers no one" (the user's own app) from
"refused SurfSense" (it may take only apps it approved), which one SDK error covers.
"""

from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    handle_auth_metadata_response,
    handle_protected_resource_response,
)

from modules.plugins.remote.sign_in.oauth.consented_client import consented_client

_PROBE = {"jsonrpc": "2.0", "id": 0, "method": "ping"}
_ACCEPT = {"accept": "application/json, text/event-stream"}


async def registration_offered(url: str, allowed_hosts: set[str]) -> bool:
    async with consented_client(allowed_hosts) as http:
        probe = await http.post(url, json=_PROBE, headers=_ACCEPT)
        issuer = None
        named = extract_resource_metadata_from_www_auth(probe)
        for candidate in build_protected_resource_metadata_discovery_urls(named, url):
            resource = await handle_protected_resource_response(
                await http.send(create_oauth_metadata_request(candidate))
            )
            if resource is not None and resource.authorization_servers:
                issuer = str(resource.authorization_servers[0])
                break
        for candidate in build_oauth_authorization_server_metadata_discovery_urls(
            issuer, url
        ):
            keep_looking, metadata = await handle_auth_metadata_response(
                await http.send(create_oauth_metadata_request(candidate))
            )
            if metadata is not None:
                return metadata.registration_endpoint is not None
            if not keep_looking:
                return False
    return False
