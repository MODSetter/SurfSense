"""What models.dev cannot say about reaching a provider, decided by a person.

models.dev writes a base URL only for providers its consumer reaches through a
generic OpenAI-compatible package; a provider with its own SDK has the URL
built into that SDK. This table fills that gap for hosted providers whose
OpenAI-compatible URL is fixed and verified, and says why a provider cannot be
reached with a plain key.

It never overrides a URL models.dev states, and it holds nothing that depends
on the user: a local server's port, or an account's own host, is theirs to
enter. A URL goes in only once checked, and the entry says where; until then
the provider asks the user for one.
"""

from dataclasses import dataclass
from typing import Any

__all__ = ["ENDPOINTS", "Fixed", "Unreachable", "stale_endpoints"]

# Where the first seven were verified: the connection form's presets, in use
# since 2.0 against each provider's live /models.
_PRESET = "SurfSense 2.0 connection preset"


@dataclass(frozen=True)
class Fixed:
    """A hosted provider's OpenAI-compatible URL, the same for every account."""

    base_url: str
    verified: str


@dataclass(frozen=True)
class Unreachable:
    """Why a plain bearer key cannot reach this provider."""

    reason: str


ENDPOINTS: dict[str, Fixed | Unreachable] = {
    "openai": Fixed("https://api.openai.com/v1", _PRESET),
    "google": Fixed("https://generativelanguage.googleapis.com/v1beta/openai", _PRESET),
    "groq": Fixed("https://api.groq.com/openai/v1", _PRESET),
    "mistral": Fixed("https://api.mistral.ai/v1", _PRESET),
    "xai": Fixed("https://api.x.ai/v1", _PRESET),
    "togetherai": Fixed("https://api.together.xyz/v1", _PRESET),
    "cerebras": Fixed("https://api.cerebras.ai/v1", _PRESET),
    "amazon-bedrock": Unreachable("Signs requests with AWS credentials, not an API key"),
    "google-vertex": Unreachable("Needs a Google Cloud sign-in, not an API key"),
    "google-vertex-anthropic": Unreachable(
        "Needs a Google Cloud sign-in, not an API key"
    ),
}


def stale_endpoints(api: dict[str, Any]) -> list[str]:
    """Reviewed entries whose provider models.dev no longer lists."""
    return sorted(provider for provider in ENDPOINTS if provider not in api)
