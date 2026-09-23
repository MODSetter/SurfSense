import asyncio
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection

DISCOVERY_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Where a model's capabilities came from. "declared" is the endpoint's own word
# for it, "catalog" the reviewed table shipped with the app. Nothing is guessed:
# an id neither source knows stays "unknown" and the picker says so.
CapabilitySource = Literal["declared", "catalog", "unknown"]


# What an endpoint's declared output modality says a model is for.
_DECLARED_AS = {
    "text": ModelType.TEXT_GEN,
    "image": ModelType.IMAGE_GEN,
    "video": ModelType.VIDEO_GEN,
    "audio": ModelType.AUDIO_GEN,
}


@dataclass(frozen=True)
class DiscoveredModel:
    name: str
    types: tuple[ModelType, ...]
    capability_source: CapabilitySource

    @property
    def capability_known(self) -> bool:
        """Whether these capabilities are known rather than merely unlisted."""
        return self.capability_source != "unknown"


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


def _entries(payload: object) -> dict[str, set[str]]:
    """Enumerate a listing into id -> declared output modalities.

    Listing and classifying are kept apart because a full catalogue can take
    more than one request, and an id may appear in several of them. Collecting
    raw modalities first means classification runs once, over the union, with no
    ranking of partial answers to reconcile afterwards.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("model endpoint did not return an OpenAI list envelope")

    entries: dict[str, set[str]] = {}
    for entry in payload["data"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        name = entry["id"].strip()
        if not name:
            continue
        entries.setdefault(name, set()).update(_modalities(entry))
    return entries


def _classify(
    name: str, modalities: set[str], catalog_provider: str | None = None
) -> DiscoveredModel:
    """Resolve one model against every source, in order, first answer winning.

    The same three doors for every model from every endpoint: what the endpoint
    published, then the reviewed catalogue, then nothing. There is no fourth
    door that guesses. A connection that names its manifest provider reads that
    provider's entry first.
    """
    if modalities:
        declared = tuple(
            model_type
            for modality, model_type in _DECLARED_AS.items()
            if modality in modalities
        )
        return DiscoveredModel(name, declared, "declared")
    catalogued = remote_lookup().classify(name, provider=catalog_provider)
    if catalogued.known:
        # Enum order, so a model's types read the same wherever they are shown.
        types = tuple(t for t in ModelType if t in catalogued.types)
        return DiscoveredModel(name, types, "catalog")
    return DiscoveredModel(name, (), "unknown")


def parse_models(payload: object) -> list[DiscoveredModel]:
    return [
        _classify(name, modalities) for name, modalities in _entries(payload).items()
    ]


async def _request_entries(
    base_url: str,
    api_key: str | None,
    *,
    image_only: bool = False,
) -> dict[str, set[str]]:
    params = {"output_modalities": "image"} if image_only else None
    async with httpx.AsyncClient(
        timeout=DISCOVERY_TIMEOUT,
        headers=_headers(api_key),
    ) as client:
        reply = await client.get(f"{base_url}/models", params=params)
        reply.raise_for_status()
        return _entries(reply.json())


async def probe_connection(base_url: str, api_key: str | None) -> list[DiscoveredModel]:
    entries = await _request_entries(base_url, api_key)
    return [_classify(name, modalities) for name, modalities in entries.items()]


async def discover_models(connection: ProviderConnection) -> list[DiscoveredModel]:
    baseline, optional = await asyncio.gather(
        _request_entries(connection.base_url, connection.api_key),
        _optional_image_entries(connection.base_url, connection.api_key),
    )
    merged = {name: set(modalities) for name, modalities in baseline.items()}
    for name, modalities in optional.items():
        merged.setdefault(name, set()).update(modalities)
    # `custom` names no manifest provider, so its models are read across all.
    provider = None if connection.catalog_provider == CUSTOM else connection.catalog_provider
    return sorted(
        (_classify(name, modalities, provider) for name, modalities in merged.items()),
        key=lambda model: model.name.casefold(),
    )


async def _optional_image_entries(
    base_url: str, api_key: str | None
) -> dict[str, set[str]]:
    """Ask again for image models, because a default listing may not hold them.

    OpenRouter serves 444 models from /models and 54 from the image-filtered
    query, 43 of which the first call never returns at all. This is enumeration,
    not classification. An endpoint that ignores the parameter answers with the
    same set, so the union is a no-op and no provider has to be recognised.
    """
    try:
        return await _request_entries(base_url, api_key, image_only=True)
    except (httpx.HTTPError, ValueError):
        return {}
