"""An OAuth plugin's sign-in, kept as one encrypted JSON blob in the row's credential.

Holds what a refresh needs without discovering again: the tokens, when the access token
expires, the client SurfSense signed in as, and where to refresh. Never logged or returned.
"""

import time

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import BaseModel

from modules.plugins.installed.models import InstalledPlugin
from shared.secrets import UnreadableSecretError

OAUTH = "oauth"


class OAuthCredential(BaseModel):
    tokens: OAuthToken
    # Epoch seconds; None when the provider gave no lifetime.
    expires_at: float | None
    client: OAuthClientInformationFull
    token_endpoint: str
    # RFC 8707's resource indicator, sent again on refresh when the sign-in sent it.
    resource: str | None = None

    def expires_within(self, seconds: float) -> bool:
        return self.expires_at is not None and self.expires_at - time.time() < seconds

    def refreshed(self, tokens: OAuthToken) -> "OAuthCredential":
        """RFC 6749 §6: a refresh may omit the refresh token and scope, which then stay."""
        kept = tokens.model_copy(
            update={
                "refresh_token": tokens.refresh_token or self.tokens.refresh_token,
                "scope": tokens.scope or self.tokens.scope,
            }
        )
        return self.model_copy(update={"tokens": kept, "expires_at": expiry(kept)})


def expiry(tokens: OAuthToken) -> float | None:
    return None if tokens.expires_in is None else time.time() + tokens.expires_in


def read_credential(plugin: InstalledPlugin) -> OAuthCredential | None:
    """None when the plugin is not signed in with OAuth, or this install cannot read it."""
    if plugin.credential_kind != OAUTH:
        return None
    try:
        stored = plugin.credential
    except UnreadableSecretError:
        return None
    return None if stored is None else OAuthCredential.model_validate_json(stored)


def write_credential(plugin: InstalledPlugin, credential: OAuthCredential) -> None:
    plugin.credential_kind = OAUTH
    plugin.credential = credential.model_dump_json(exclude_none=True)
