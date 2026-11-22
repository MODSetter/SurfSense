"""How a provider lets an app register, read from its authorization server's metadata.

Read before registering, so a provider registering no app goes straight to the user's own
without a request sent only to fail; and after a refused one, to tell "registers no one"
from "refused SurfSense", which one SDK error covers. The hosts are allowed by then.
"""

from dataclasses import dataclass

from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    handle_auth_metadata_response,
    handle_protected_resource_response,
)

from modules.plugins.remote.sign_in.oauth.consented_client import consented_client


@dataclass(frozen=True)
class RegistrationOffer:
    # A `registration_endpoint`: dynamic registration.
    registers: bool
    # Client ID metadata documents, which a packaged SurfSense signs in with.
    client_documents: bool


_PROBE = {"jsonrpc": "2.0", "id": 0, "method": "ping"}
_ACCEPT = {"accept": "application/json, text/event-stream"}


async def registration_offer(
    url: str, allowed_hosts: set[str]
) -> RegistrationOffer | None:
    """None when the provider publishes no metadata, as an older server may not."""
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
                return RegistrationOffer(
                    registers=metadata.registration_endpoint is not None,
                    client_documents=metadata.client_id_metadata_document_supported
                    is True,
                )
            if not keep_looking:
                return None
    return None
