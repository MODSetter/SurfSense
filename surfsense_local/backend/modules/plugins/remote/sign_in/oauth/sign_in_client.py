"""Who SurfSense signs in as, and where the provider sends the browser back.

A packaged app signs in as SurfSense's one app: its client ID metadata document on the
plugin host, whose only redirect is the plugin host's callback page. A developer's build
has no plugin host serving those, so it registers dynamically with the API's own loopback
callback (RFC 8252).
"""

from dataclasses import dataclass

from mcp.shared.auth import OAuthClientMetadata

from modules.plugins.lists.registry import registry_origin
from shared.config import get_plugin_host_settings

CLIENT_METADATA_URL = "https://plugins.surfsense.com/oauth/client.json"
HOSTED_CALLBACK = "https://plugins.surfsense.com/oauth/callback"
CALLBACK_PATH = "/plugins/oauth/callback"


@dataclass(frozen=True)
class SignInClient:
    redirect_uri: str
    # None: register dynamically. The SDK uses it only where the server supports one.
    client_metadata_url: str | None


def sign_in_client(port: int) -> SignInClient:
    if registry_origin.reads_repository() or get_plugin_host_settings().plugin_host_url:
        return SignInClient(f"http://127.0.0.1:{port}{CALLBACK_PATH}", None)
    return SignInClient(HOSTED_CALLBACK, CLIENT_METADATA_URL)


def client_metadata(
    client: SignInClient, scopes: list[str] | None, confidential: bool = False
) -> OAuthClientMetadata:
    """A public client: PKCE protects the sign-in, and no secret ships in the app.

    `confidential` registers for a secret the provider issues to this install alone,
    for a provider that registers no public client; it is kept with the sign-in.
    """
    return OAuthClientMetadata(
        client_name="SurfSense",
        redirect_uris=[client.redirect_uri],
        token_endpoint_auth_method="client_secret_post" if confidential else "none",
        grant_types=["authorization_code", "refresh_token"],
        scope=" ".join(scopes) if scopes else None,
    )
