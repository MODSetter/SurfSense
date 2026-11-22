"""One sign-in through the MCP SDK's OAuth client: discovery, registration, PKCE, the code
exchanged for tokens. SurfSense supplies where the browser goes and how the code comes back.

The SDK runs its flow inside an HTTP request's auth: an unsigned request to the server is
refused, the flow runs, and the request is sent again signed.
"""

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from mcp.client.auth import OAuthClientProvider, OAuthFlowError
from mcp.shared.auth import AuthorizationCodeResult

from modules.plugins.remote.sign_in.oauth.consented_client import consented_client
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAuthCredential
from modules.plugins.remote.sign_in.oauth.pending_storage import PendingStorage
from modules.plugins.remote.sign_in.oauth.sign_in_client import (
    SignInClient,
    client_metadata,
)

_PROBE = {"jsonrpc": "2.0", "id": 0, "method": "ping"}
_ACCEPT = {"accept": "application/json, text/event-stream"}


async def sign_in(
    url: str,
    client: SignInClient,
    storage: PendingStorage,
    scopes: list[str] | None,
    allowed_hosts: set[str],
    open_browser: Callable[[str], Awaitable[None]],
    code_returned: Callable[[], Awaitable[AuthorizationCodeResult]],
    confidential: bool = False,
) -> OAuthCredential:
    provider = OAuthClientProvider(
        server_url=url,
        client_metadata=client_metadata(client, scopes, confidential),
        storage=storage,
        redirect_handler=open_browser,
        callback_handler=code_returned,
        # A client metadata document names a public client; one with a secret registers.
        client_metadata_url=None if confidential else client.client_metadata_url,
    )
    async with consented_client(allowed_hosts) as http:
        await http.post(url, json=_PROBE, headers=_ACCEPT, auth=provider)
    if storage.tokens is None or storage.client is None:
        raise OAuthFlowError("the server did not ask to sign in")
    context = provider.context
    metadata = context.oauth_metadata
    origin = urlsplit(url)._replace(path="", query="", fragment="").geturl()
    return OAuthCredential(
        tokens=storage.tokens,
        expires_at=storage.expires_at,
        client=storage.client,
        # The SDK's own fallback when the server published no metadata.
        token_endpoint=str(metadata.token_endpoint) if metadata else f"{origin}/token",
        resource=(
            context.get_resource_url()
            if context.should_include_resource_param(context.protocol_version)
            else None
        ),
    )
