"""Where a ChatGPT plan signs in and answers. The one place the source is named.

From OpenAI's "Sign in with ChatGPT" docs for open-source apps
(developers.openai.com/siwc/token-sharing-open-source) and the issuer's own
discovery document at auth.openai.com/.well-known/openid-configuration.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# A first sign-in registers this install as a client; OpenAI answers with the
# client id every later request uses.
DYNAMIC_CLIENT = "dynamic_agent_client"
AGENT_NAME = "SurfSense"
RESOURCE = "https://api.openai.com/v1"
SCOPE = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
CALLBACK_PATH = "/callback"


class ChatGPTEndpoints(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SURFSENSE_LOCAL_CHATGPT_")

    auth_url: str = "https://auth.openai.com"
    api_url: str = "https://api.openai.com/v1"

    @property
    def authorize_url(self) -> str:
        return f"{self.auth_url}/api/accounts/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.auth_url}/api/accounts/oauth/token"

    @property
    def revoke_url(self) -> str:
        # The discovery document's `revocation_endpoint`; a public client may call it.
        return f"{self.auth_url}/api/accounts/oauth/revoke"

    @property
    def jwks_url(self) -> str:
        return f"{self.auth_url}/.well-known/jwks.json"


@lru_cache
def get_endpoints() -> ChatGPTEndpoints:
    return ChatGPTEndpoints()
