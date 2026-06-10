"""Connection verification, model discovery, and capability probing."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import litellm

from app.db import Connection, ConnectionProtocol, Model, ModelSource
from app.services.model_resolver import ensure_v1, to_litellm

logger = logging.getLogger(__name__)

VERIFY_TIMEOUT_SECONDS = 8.0
DISCOVERY_TIMEOUT_SECONDS = 15.0
TEST_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class VerifyResult:
    status: str
    ok: bool
    message: str = ""


def _auth_headers(conn: Connection) -> dict[str, str]:
    if not conn.api_key:
        return {}
    return {"Authorization": f"Bearer {conn.api_key}"}


def _docker_hint(url: str | None, exc_or_status: Any) -> str:
    raw = str(exc_or_status)
    if not url:
        return raw
    if "localhost" in url or "127.0.0.1" in url:
        return (
            f"{raw}. The backend is running inside Docker; localhost means the "
            "backend container. Use host.docker.internal and make sure the model "
            "server listens on 0.0.0.0."
        )
    if "host.docker.internal" in url and ("refused" in raw.lower() or "connect" in raw.lower()):
        return (
            f"{raw}. The host is reachable only if your local model server is "
            "listening on 0.0.0.0. On Linux Docker, add "
            "`host.docker.internal:host-gateway` to extra_hosts."
        )
    return raw


async def verify_connection(conn: Connection) -> VerifyResult:
    if not conn.base_url and conn.protocol in (
        ConnectionProtocol.OLLAMA,
        ConnectionProtocol.OPENAI_COMPATIBLE,
    ):
        return VerifyResult("UNREACHABLE", False, "Base URL is required.")

    if conn.protocol == ConnectionProtocol.OLLAMA:
        url = f"{conn.base_url.rstrip('/')}/api/version"
    elif conn.protocol == ConnectionProtocol.OPENAI_COMPATIBLE:
        url = f"{ensure_v1(conn.base_url)}/models"
    else:
        # Native providers do not share one cheap health endpoint. The model
        # probe exercises the real path and is the authoritative check.
        return VerifyResult("OK", True, "Native provider configuration accepted.")

    try:
        async with httpx.AsyncClient(timeout=VERIFY_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_headers(conn))
        if response.status_code in (401, 403):
            return VerifyResult("AUTH_FAILED", False, "Authentication failed.")
        if response.status_code == 404:
            if conn.protocol == ConnectionProtocol.OLLAMA and url.endswith("/v1/models"):
                message = "Ollama native API should not use /v1."
            elif conn.protocol == ConnectionProtocol.OPENAI_COMPATIBLE:
                message = "OpenAI-compatible servers should expose /v1/models."
            else:
                message = "Endpoint returned 404."
            return VerifyResult("NOT_FOUND", False, message)
        response.raise_for_status()
        return VerifyResult("OK", True, "Connection verified.")
    except httpx.ConnectError as exc:
        return VerifyResult("UNREACHABLE", False, _docker_hint(conn.base_url, exc))
    except httpx.TimeoutException as exc:
        return VerifyResult("UNREACHABLE", False, f"Connection timed out: {exc}")
    except httpx.HTTPError as exc:
        return VerifyResult("UNREACHABLE", False, _docker_hint(conn.base_url, exc))


async def persist_verification(conn: Connection) -> VerifyResult:
    result = await verify_connection(conn)
    conn.last_verified_at = datetime.now(UTC)
    conn.last_status = result.status
    conn.last_error = "" if result.ok else result.message
    return result


def _litellm_capabilities(model_string: str, model_id: str) -> dict[str, bool]:
    capabilities = {
        "chat": True,
        "vision": False,
        "tools": False,
        "image_gen": False,
        "embedding": False,
    }
    with contextlib.suppress(Exception):
        capabilities["vision"] = bool(litellm.supports_vision(model=model_string))
    with contextlib.suppress(Exception):
        capabilities["tools"] = bool(litellm.supports_function_calling(model=model_string))
    try:
        info = litellm.model_cost.get(model_string) or litellm.model_cost.get(model_id) or {}
        mode = str(info.get("mode") or "")
        capabilities["embedding"] = mode == "embedding"
        capabilities["image_gen"] = mode in {"image_generation", "image_generation_model"}
    except Exception:
        pass
    return capabilities


def derive_capabilities(conn: Connection, model_id: str, metadata: dict | None = None) -> dict[str, bool]:
    metadata = metadata or {}
    if conn.protocol == ConnectionProtocol.OLLAMA:
        caps = metadata.get("capabilities") or []
        capabilities = {
            "chat": True,
            "vision": "vision" in caps,
            "tools": False,
            "image_gen": False,
            "embedding": "embedding" in caps,
        }
        return capabilities

    model_string, _ = to_litellm(conn, model_id)
    return _litellm_capabilities(model_string, model_id)


async def discover_models(conn: Connection) -> list[dict[str, Any]]:
    if conn.protocol == ConnectionProtocol.OLLAMA:
        url = f"{conn.base_url.rstrip('/')}/api/tags"
        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_headers(conn))
        response.raise_for_status()
        models = response.json().get("models", [])
        return [
            {
                "model_id": item.get("model") or item.get("name"),
                "display_name": item.get("name") or item.get("model"),
                "source": ModelSource.DISCOVERED,
                "capabilities": derive_capabilities(conn, item.get("model") or item.get("name"), item),
                "metadata": item,
            }
            for item in models
            if item.get("model") or item.get("name")
        ]

    if conn.protocol == ConnectionProtocol.OPENAI_COMPATIBLE:
        url = f"{ensure_v1(conn.base_url)}/models"
        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_headers(conn))
        response.raise_for_status()
        models = response.json().get("data", [])
        return [
            {
                "model_id": item.get("id"),
                "display_name": item.get("name") or item.get("id"),
                "source": ModelSource.DISCOVERED,
                "capabilities": derive_capabilities(conn, item.get("id"), item),
                "metadata": item,
            }
            for item in models
            if item.get("id")
        ]

    # Native providers rely on curated/global catalog entries or manual rows.
    return []


async def test_model(conn: Connection, model: Model) -> VerifyResult:
    model_string, kwargs = to_litellm(conn, model.model_id)
    try:
        await litellm.acompletion(
            model=model_string,
            messages=[{"role": "user", "content": "Hello"}],
            timeout=TEST_TIMEOUT_SECONDS,
            **kwargs,
        )
    except Exception as exc:
        return VerifyResult("UNREACHABLE", False, str(exc))

    model.capabilities_verified = {
        **(model.capabilities_verified or {}),
        "chat": True,
    }
    return VerifyResult("OK", True, "Model test succeeded.")


__all__ = [
    "VerifyResult",
    "derive_capabilities",
    "discover_models",
    "persist_verification",
    "test_model",
    "verify_connection",
]
