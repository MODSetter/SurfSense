import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from modules.llm.models import ProviderConnection

DISCOVERY_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@dataclass(frozen=True)
class DiscoveredModel:
    name: str
    capabilities: tuple[str, ...]
    capability_known: bool


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
        capabilities: list[str] = []
        if "text" in modalities:
            capabilities.append("completion")
        if "image" in modalities:
            capabilities.append("image_generation")
        models.append(
            DiscoveredModel(
                name=name,
                capabilities=tuple(capabilities),
                capability_known=bool(modalities),
            )
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
            capability_known=existing.capability_known or model.capability_known,
        )
    return sorted(merged.values(), key=lambda model: model.name.casefold())


async def _optional_image_models(
    base_url: str, api_key: str | None
) -> list[DiscoveredModel]:
    try:
        return await _request_models(base_url, api_key, image_only=True)
    except (httpx.HTTPError, ValueError):
        return []
