"""Who SurfSense signs in as, and where the provider sends the browser back.

A packaged app signs in as SurfSense's one app: its client ID metadata document on the
plugin host, whose only redirect is the plugin host's callback page. A developer's build
has no plugin host serving those, so it registers dynamically with the API's own loopback
callback (RFC 8252). In the Docker image a browser on another device signs in at its own
origin: as the instance's own document on its public domain, by registering on a LAN.
"""

from dataclasses import dataclass

from mcp.shared.auth import OAuthClientMetadata

from api.config import get_settings
from modules.plugins.lists.registry import registry_origin
from modules.plugins.remote.sign_in.oauth.browser_origin import BrowserOrigin
from shared.config import get_plugin_host_settings

CLIENT_METADATA_URL = "https://plugins.surfsense.com/oauth/client.json"
HOSTED_CALLBACK = "https://plugins.surfsense.com/oauth/callback"
CALLBACK_PATH = "/plugins/oauth/callback"
CLIENT_DOCUMENT_PATH = "/plugins/oauth/client.json"


@dataclass(frozen=True)
class SignInClient:
    redirect_uri: str
    # None: register dynamically. The SDK uses it only where the server supports one.
    client_metadata_url: str | None


def sign_in_client(origin: BrowserOrigin) -> SignInClient:
    if not origin.is_loopback:
        document = (
            f"{origin.url}{CLIENT_DOCUMENT_PATH}" if _public_domain(origin) else None
        )
        return SignInClient(f"{origin.url}{CALLBACK_PATH}", document)
    if registry_origin.reads_repository() or get_plugin_host_settings().plugin_host_url:
        return SignInClient(f"http://127.0.0.1:{origin.port}{CALLBACK_PATH}", None)
    return SignInClient(HOSTED_CALLBACK, CLIENT_METADATA_URL)


def _public_domain(origin: BrowserOrigin) -> bool:
    """Only a domain the provider can fetch a document from, over HTTPS."""
    domain = get_settings().domain
    return origin.scheme == "https" and domain is not None and origin.host == domain


def client_document(origin: BrowserOrigin) -> dict | None:
    """The instance's own client ID metadata document, for its public domain only:
    its one redirect is the domain's own callback."""
    if origin.is_loopback or not _public_domain(origin):
        return None
    return {
        "client_id": f"{origin.url}{CLIENT_DOCUMENT_PATH}",
        "client_name": "SurfSense",
        "client_uri": "https://surfsense.com",
        "redirect_uris": [f"{origin.url}{CALLBACK_PATH}"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


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
