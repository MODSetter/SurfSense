"""models.dev in the app's own words: evidence and display fields, nothing else.

models.dev is written for the Vercel AI SDK, so it names JavaScript packages,
environment variables and prices this app never reads. What survives is what
the classifier, support and the screen read, under the provider that serves
the model, because the same id means what each provider says it means.
"""

import re
from typing import Any
from urllib.parse import urlsplit

from remote_manifest.endpoints import ENDPOINTS, Fixed, Unreachable

__all__ = ["translate"]

# The packages whose consumer speaks the OpenAI API at the stated URL.
OPENAI_WIRE = frozenset(
    {"@ai-sdk/openai-compatible", "@ai-sdk/openai", "@openrouter/ai-sdk-provider"}
)
# What a person would call the protocol behind the rest.
PROTOCOLS = {
    "@ai-sdk/anthropic": "anthropic",
    "@ai-sdk/google": "google",
    "@ai-sdk/google-vertex/anthropic": "vertex-anthropic",
    "@ai-sdk/amazon-bedrock": "bedrock",
    "@ai-sdk/amazon-bedrock/mantle": "bedrock",
}
_PROTOCOL_NAMES = {"anthropic": "Anthropic's API", "google": "Google's Gemini API"}
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
_TEMPLATE_VARIABLE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def translate(
    api: dict[str, Any], endpoints: dict[str, Fixed | Unreachable] = ENDPOINTS
) -> dict[str, Any]:
    """The whole models.dev listing, keyed provider then model."""
    return {
        "providers": {
            provider_id: _provider(provider_id, provider, endpoints)
            for provider_id, provider in api.items()
        }
    }


def _provider(
    provider_id: str,
    provider: dict[str, Any],
    endpoints: dict[str, Fixed | Unreachable],
) -> dict[str, Any]:
    return {
        "name": provider["name"],
        "doc": provider.get("doc"),
        "connect": _connect(provider, endpoints.get(provider_id)),
        "models": {
            model_id: _model(model)
            for model_id, model in (provider.get("models") or {}).items()
        },
    }


def _model(model: dict[str, Any]) -> dict[str, Any]:
    limit = model.get("limit") or {}
    return {
        "name": model.get("name") or model["id"],
        "family": model.get("family"),
        "description": model.get("description"),
        "release_date": model.get("release_date"),
        "status": model.get("status"),
        "modalities": model.get("modalities") or {"input": [], "output": []},
        # 0 means "not a token model" upstream, which is not a window.
        "context": _positive(limit.get("context")),
        "output_limit": _positive(limit.get("output")),
        # None is not no: an absent field stays absent rather than becoming false.
        "tool_call": model.get("tool_call"),
        "reasoning": model.get("reasoning"),
        "reasoning_options": model.get("reasoning_options"),
        "structured_output": model.get("structured_output"),
        "temperature": model.get("temperature"),
        "call": _call(model),
    }


def _connect(provider: dict[str, Any], reviewed: Fixed | Unreachable | None) -> dict[str, Any]:
    """How a connection reaches this provider, from models.dev and the reviewed table."""
    url = provider.get("api")
    package = provider.get("npm")
    if isinstance(reviewed, Unreachable):
        return _state("unreachable", reason=reviewed.reason)
    if url and package not in OPENAI_WIRE:
        return _state("unreachable", reason=f"Speaks {_protocol_name(package)}, which SurfSense does not")
    if url and _TEMPLATE_VARIABLE.search(url):
        fields = [
            {"name": name, "label": name.replace("_", " ").capitalize()}
            for name in dict.fromkeys(_TEMPLATE_VARIABLE.findall(url))
        ]
        return _state("needs_account_details", url, "models.dev", fields)
    if url:
        return _state("ready", url, "models.dev")
    if isinstance(reviewed, Fixed):
        return _state("ready", reviewed.base_url, "reviewed")
    # Nothing is guessed: the user enters the URL.
    return _state("needs_url")


def _state(
    status: str,
    base_url: str | None = None,
    origin: str | None = None,
    account_fields: list[dict[str, str]] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    local = bool(base_url) and urlsplit(base_url).hostname in _LOOPBACK
    return {
        "status": status,
        "base_url": base_url,
        "base_url_origin": origin,
        "account_fields": account_fields or [],
        # A loopback server is the user's own and takes no key.
        "key": "none" if local else "required",
        "local": local,
        "reason": reason,
    }


def _call(model: dict[str, Any]) -> dict[str, str] | None:
    """How this model is called, when it differs from its provider."""
    override = model.get("provider") or {}
    package = override.get("npm")
    if package and package not in OPENAI_WIRE:
        return {"protocol": PROTOCOLS.get(package, package)}
    if override.get("shape") == "responses":
        return {"route": "responses"}
    return None


def _protocol_name(package: str | None) -> str:
    protocol = PROTOCOLS.get(package or "", package or "an unknown protocol")
    return _PROTOCOL_NAMES.get(protocol, f"the {protocol} protocol")


def _positive(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None
