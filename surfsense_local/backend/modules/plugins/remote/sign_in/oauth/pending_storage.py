"""The SDK's token storage for a sign-in under way: memory only.

Nothing reaches the plugin's row until the callback succeeds, so an abandoned sign-in
leaves no tokens and no registered client behind.
"""

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from modules.plugins.remote.sign_in.oauth.oauth_credential import expiry


class PendingStorage:
    def __init__(self, client: OAuthClientInformationFull | None = None) -> None:
        # A pre-registered client, or the one a previous sign-in registered.
        self.client = client
        self.tokens: OAuthToken | None = None
        self.expires_at: float | None = None

    async def get_tokens(self) -> OAuthToken | None:
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.tokens = tokens
        self.expires_at = expiry(tokens)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self.client

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.client = client_info
