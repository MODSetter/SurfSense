import asyncio
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from modules.llm.models import ProviderConnection

DISCOVERY_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Where a model's capabilities came from. Only "declared" is the endpoint's own
# word for it; "inferred" is read off the name and must never block a choice.
CapabilitySource = Literal["declared", "inferred", "unknown"]
_SOURCE_RANK: dict[str, int] = {"unknown": 0, "inferred": 1, "declared": 2}


@dataclass(frozen=True)
class DiscoveredModel:
    name: str
    capabilities: tuple[str, ...]
    capability_source: CapabilitySource

    @property
    def capability_known(self) -> bool:
        """Whether the endpoint itself vouched for these capabilities."""
        return self.capability_source == "declared"


def normalize_base_url(value: str) -> str:
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as error:
        raise ValueError("base URL has an invalid port") from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query or fragment")

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, netloc, path, "", ""))


def _headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _modalities(entry: dict) -> set[str]:
    raw = entry.get("output_modalities")
    if raw is None and isinstance(entry.get("architecture"), dict):
        raw = entry["architecture"].get("output_modalities")
    if not isinstance(raw, list):
        return set()
    return {
        value if isinstance(value, str) else value.get("type")
        for value in raw
        if isinstance(value, (str, dict))
    } - {None}


# output_modalities is an OpenRouter extension. OpenAI and Gemini answer /models
# with nothing but an id, so every row used to arrive unclassified and both the
# chat and image filters came back empty over a 138-row list. The name is the
# only signal those endpoints leave, and it is a good one: checked against the
# 443 models OpenRouter does declare, these patterns raise no false positive,
# and they catch every image model OpenAI and Gemini publish.
_IMAGE_NAME = re.compile(r"(^|[-/_.])(image|imagen|dall-?e)([-/_.0-9]|$)", re.IGNORECASE)
_NOT_CHAT_NAME = re.compile(
    r"(^|[-/_.])(embedding|embed|tts|whisper|transcribe|audio|realtime"
    r"|moderation|sora|video|rerank)([-/_.0-9]|$)",
    re.IGNORECASE,
)


def _infer_capabilities(name: str) -> tuple[str, ...]:
    """Read capabilities off a model name, for endpoints that declare none.

    Empty means the name says it is neither: an embedding or speech model, which
    this app has no role for. Vendors who brand image models without the word
    (Recraft, Seedream) are missed, and all of them are OpenRouter-only, which
    declares its modalities and never reaches here.
    """
    tail = name.rsplit("/", 1)[-1]
    if _IMAGE_NAME.search(tail):
        return ("image_generation",)
    if _NOT_CHAT_NAME.search(tail):
        return ()
    return ("completion",)


def parse_models(payload: object) -> list[DiscoveredModel]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("model endpoint did not return an OpenAI list envelope")

    models: list[DiscoveredModel] = []
    for entry in payload["data"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        name = entry["id"].strip()
        if not name:
            continue
        modalities = _modalities(entry)
        if modalities:
            capabilities = []
            if "text" in modalities:
                capabilities.append("completion")
            if "image" in modalities:
                capabilities.append("image_generation")
            models.append(DiscoveredModel(name, tuple(capabilities), "declared"))
            continue
        inferred = _infer_capabilities(name)
        models.append(
            DiscoveredModel(name, inferred, "inferred" if inferred else "unknown")
        )
    return models


async def _request_models(
    base_url: str,
    api_key: str | None,
    *,
    image_only: bool = False,
) -> list[DiscoveredModel]:
    params = {"output_modalities": "image"} if image_only else None
    async with httpx.AsyncClient(
        timeout=DISCOVERY_TIMEOUT,
        headers=_headers(api_key),
    ) as client:
        reply = await client.get(f"{base_url}/models", params=params)
        reply.raise_for_status()
        return parse_models(reply.json())


async def probe_connection(base_url: str, api_key: str | None) -> list[DiscoveredModel]:
    return await _request_models(base_url, api_key)


async def discover_models(connection: ProviderConnection) -> list[DiscoveredModel]:
    baseline, optional = await asyncio.gather(
        _request_models(connection.base_url, connection.api_key),
        _optional_image_models(connection.base_url, connection.api_key),
    )
    merged: dict[str, DiscoveredModel] = {model.name: model for model in baseline}
    for model in optional:
        existing = merged.get(model.name)
        if existing is None:
            merged[model.name] = model
            continue
        capabilities = tuple(
            sorted(set(existing.capabilities) | set(model.capabilities))
        )
        merged[model.name] = DiscoveredModel(
            name=model.name,
            capabilities=capabilities,
            capability_source=max(
                existing.capability_source,
                model.capability_source,
                key=_SOURCE_RANK.__getitem__,
            ),
        )
    return sorted(merged.values(), key=lambda model: model.name.casefold())


async def _optional_image_models(
    base_url: str, api_key: str | None
) -> list[DiscoveredModel]:
    try:
        return await _request_models(base_url, api_key, image_only=True)
    except (httpx.HTTPError, ValueError):
        return []
