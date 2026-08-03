"""Connection verification, model discovery, and capability probing."""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import anyio
import httpx
import litellm

from app.db import Connection, Model, ModelSource
from app.services.model_resolver import to_litellm
from app.services.openrouter_model_normalizer import normalize_openrouter_models
from app.services.provider_registry import Transport, provider_label, spec_for
from app.services.requesty_model_normalizer import normalize_requesty_models

logger = logging.getLogger(__name__)

VERIFY_TIMEOUT_SECONDS = 8.0
DISCOVERY_TIMEOUT_SECONDS = 15.0
TEST_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class VerifyResult:
    status: str
    ok: bool
    message: str = ""


class ModelDiscoveryError(Exception):
    """User-correctable discovery failure for provider configuration issues."""


def _auth_headers(conn: Connection) -> dict[str, str]:
    if not conn.api_key:
        return {}
    return {"Authorization": f"Bearer {conn.api_key}"}


def _anthropic_headers(conn: Connection) -> dict[str, str]:
    headers = {"anthropic-version": "2023-06-01"}
    if conn.api_key:
        headers["x-api-key"] = conn.api_key
    return headers


def _base_url_or_default(conn: Connection) -> str | None:
    if conn.base_url:
        return conn.base_url.rstrip("/")
    if conn.provider == "openai":
        return "https://api.openai.com/v1"
    if conn.provider == "anthropic":
        return "https://api.anthropic.com/v1"
    return spec_for(conn.provider).default_base_url


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
    if "host.docker.internal" in url and (
        "refused" in raw.lower() or "connect" in raw.lower()
    ):
        return (
            f"{raw}. The host is reachable only if your local model server is "
            "listening on 0.0.0.0. On Linux Docker, add "
            "`host.docker.internal:host-gateway` to extra_hosts."
        )
    return raw


def _provider_detail(raw: str, limit: int = 300) -> str:
    """Bound provider error text; LiteLLM and gateway bodies can be large."""
    detail = " ".join(raw.split())
    return detail if len(detail) <= limit else f"{detail[:limit]}…"


def _provider_error(
    conn: Connection,
    *,
    status_code: int,
    detail: str,
    model_id: str | None = None,
) -> VerifyResult:
    """Report a provider response without misclassifying it as unreachable."""
    target = f"model '{model_id}'" if model_id else _base_url_or_default(conn)
    return VerifyResult(
        "PROVIDER_ERROR",
        False,
        f"{provider_label(conn.provider)} returned HTTP {status_code} for "
        f"{target}. {_provider_detail(detail)}",
    )


def _model_test_error(conn: Connection, model_id: str, exc: Exception) -> VerifyResult:
    provider_name = provider_label(conn.provider)
    raw = str(exc)
    normalized = raw.lower()
    exc_name = exc.__class__.__name__.lower()
    status_code = getattr(exc, "status_code", None)

    logger.info(
        "Model test failed for provider=%s model=%s: %s",
        conn.provider,
        model_id,
        raw,
    )

    if status_code == 400 and "api key" in normalized:
        return VerifyResult(
            "AUTH_FAILED",
            False,
            f"Authentication failed. Check your {provider_name} credentials and try again.",
        )

    if status_code in (401, 403) or "authentication" in exc_name or "401" in normalized:
        return VerifyResult(
            "AUTH_FAILED",
            False,
            f"Authentication failed. Check your {provider_name} credentials and try again.",
        )

    if status_code == 404 or "notfound" in exc_name or "not found" in normalized:
        if conn.provider == "azure":
            message = (
                "Azure OpenAI deployment was not found. Check the deployment name, "
                "API version, and endpoint."
            )
        else:
            message = f"Model '{model_id}' was not found on {provider_name}."
        return VerifyResult("NOT_FOUND", False, message)

    if status_code == 429 or "ratelimit" in exc_name or "rate limit" in normalized:
        return VerifyResult(
            "RATE_LIMITED",
            False,
            f"{provider_name} rate limited the model test. Try again later or check your provider for possible insufficient quotas or unavailable model.",
        )

    if "timeout" in exc_name or "timed out" in normalized:
        return VerifyResult(
            "TIMEOUT",
            False,
            f"{provider_name} did not respond in time. Check the endpoint and try again.",
        )

    # LiteLLM can wrap a clean HTTP response in APIConnectionError. A status
    # code means the provider answered; only its absence is a transport failure.
    if isinstance(status_code, int) and status_code >= 400:
        return _provider_error(
            conn,
            status_code=status_code,
            detail=raw,
            model_id=model_id,
        )

    if "connection" in exc_name or "connect" in normalized:
        return VerifyResult(
            "UNREACHABLE",
            False,
            _docker_hint(
                _base_url_or_default(conn),
                f"Could not reach {provider_name}. Check the endpoint and try again.",
            ),
        )

    return VerifyResult(
        "UNREACHABLE",
        False,
        f"Could not test model '{model_id}' on {provider_name}. Check the credentials, endpoint, and model name.",
    )


def _openai_compatible_404_hint(url: str) -> str:
    return f"Got 404 from {url}. Check your API Base URL."


async def verify_connection(conn: Connection) -> VerifyResult:
    spec = spec_for(conn.provider)
    base_url = _base_url_or_default(conn)
    if spec.base_url_required and not base_url:
        return VerifyResult("UNREACHABLE", False, "Base URL is required.")

    if spec.discovery == "lm_studio_models":
        try:
            await _discover_lm_studio_models(conn)
            return VerifyResult("OK", True, "Connection verified.")
        except ModelDiscoveryError as exc:
            return VerifyResult("UNREACHABLE", False, str(exc))
        except httpx.ConnectError as exc:
            return VerifyResult("UNREACHABLE", False, _docker_hint(base_url, exc))
        except httpx.TimeoutException as exc:
            return VerifyResult("UNREACHABLE", False, f"Connection timed out: {exc}")
        except httpx.HTTPStatusError as exc:
            return _provider_error(
                conn,
                status_code=exc.response.status_code,
                detail=exc.response.text,
            )
        except httpx.HTTPError as exc:
            return VerifyResult("UNREACHABLE", False, _docker_hint(base_url, exc))
    elif spec.transport == Transport.OLLAMA and base_url:
        url = f"{base_url.rstrip('/')}/api/version"
    elif spec.discovery in {"openai_models", "openrouter", "requesty"} and base_url:
        url = f"{base_url.rstrip('/')}/models"  # verbatim; user owns the path
    elif spec.discovery == "anthropic_models" and base_url:
        url = f"{base_url.rstrip('/')}/models"
    else:
        return VerifyResult(
            "OK", True, "Connection uses provider-native authentication."
        )

    try:
        async with httpx.AsyncClient(timeout=VERIFY_TIMEOUT_SECONDS) as client:
            headers = (
                _anthropic_headers(conn)
                if spec.auth_style == "x-api-key"
                else _auth_headers(conn)
            )
            response = await client.get(url, headers=headers)
        if response.status_code in (401, 403):
            return VerifyResult("AUTH_FAILED", False, "Authentication failed.")
        if response.status_code == 404:
            if spec.transport == Transport.OLLAMA and url.endswith("/v1/models"):
                message = "Ollama native API should not use /v1."
            elif spec.transport == Transport.OPENAI_COMPATIBLE:
                message = _openai_compatible_404_hint(url)
            else:
                message = f"Endpoint returned 404 for {url}."
            return VerifyResult("NOT_FOUND", False, message)
        response.raise_for_status()
        return VerifyResult("OK", True, "Connection verified.")
    except httpx.ConnectError as exc:
        return VerifyResult("UNREACHABLE", False, _docker_hint(base_url, exc))
    except httpx.TimeoutException as exc:
        return VerifyResult("UNREACHABLE", False, f"Connection timed out: {exc}")
    except httpx.HTTPStatusError as exc:
        return _provider_error(
            conn,
            status_code=exc.response.status_code,
            detail=exc.response.text,
        )
    except httpx.HTTPError as exc:
        return VerifyResult("UNREACHABLE", False, _docker_hint(base_url, exc))


def _discovery_error_message(conn: Connection, exc: httpx.HTTPError) -> str:
    base_url = _base_url_or_default(conn)
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in (401, 403):
            return "Authentication failed while discovering models."
        if status_code == 404:
            spec = spec_for(conn.provider)
            attempted = str(exc.request.url)
            if spec.transport == Transport.OPENAI_COMPATIBLE:
                return _openai_compatible_404_hint(attempted)
            return f"Model discovery endpoint returned 404 for {attempted}."
        return f"Model discovery failed with HTTP {status_code}."
    if isinstance(exc, httpx.TimeoutException):
        return f"Model discovery timed out: {exc}"
    return _docker_hint(base_url, exc)


def _litellm_info(model_string: str, model_id: str) -> dict[str, Any]:
    with contextlib.suppress(Exception):
        info = litellm.get_model_info(model=model_string)
        if isinstance(info, dict):
            return info
    return (
        litellm.model_cost.get(model_string) or litellm.model_cost.get(model_id) or {}
    )


def _classify_from_litellm(model_string: str, model_id: str) -> dict[str, Any]:
    info = _litellm_info(model_string, model_id)
    mode = info.get("mode")
    supports_image_input = False
    supports_tools = False
    with contextlib.suppress(Exception):
        supports_image_input = bool(litellm.supports_vision(model=model_string))
    with contextlib.suppress(Exception):
        supports_tools = bool(litellm.supports_function_calling(model=model_string))
    return {
        "supports_chat": mode in (None, "chat", "completion", "responses"),
        "max_input_tokens": info.get("max_input_tokens") or info.get("max_tokens"),
        "supports_image_input": supports_image_input,
        "supports_tools": supports_tools,
        "supports_image_generation": mode
        in {"image_generation", "image_generation_model"},
    }


def derive_capabilities(
    conn: Connection, model_id: str, metadata: dict | None = None
) -> dict[str, Any]:
    metadata = metadata or {}
    spec = spec_for(conn.provider)
    model_string, _ = to_litellm(conn, model_id)
    facts = _classify_from_litellm(model_string, model_id)
    if spec.transport == Transport.OLLAMA:
        caps = set(metadata.get("capabilities") or [])
        details = metadata.get("details") or {}
        facts.update(
            {
                "supports_chat": "embedding" not in caps,
                "supports_image_input": "vision" in caps
                or facts["supports_image_input"],
                "supports_tools": "tools" in caps or facts["supports_tools"],
                "supports_image_generation": False,
                "max_input_tokens": metadata.get("context_length")
                or metadata.get("num_ctx")
                or details.get("context_length")
                or facts["max_input_tokens"],
            }
        )
    return facts


async def _discover_openai_shaped_models(
    conn: Connection, base_url: str | None
) -> list[dict[str, Any]]:
    resolved_base_url = base_url or _base_url_or_default(conn)
    if not resolved_base_url:
        return []

    url = f"{resolved_base_url.rstrip('/')}/models"  # verbatim; user owns the path
    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        response = await client.get(url, headers=_auth_headers(conn))
    response.raise_for_status()

    results: list[dict[str, Any]] = []
    for item in response.json().get("data", []):
        model_id = item.get("id")
        if not model_id:
            continue
        results.append(
            {
                "model_id": model_id,
                "display_name": item.get("name") or model_id,
                "source": ModelSource.DISCOVERED,
                **derive_capabilities(conn, model_id, item),
                "metadata": item,
            }
        )
    return results


def _lm_studio_server_root(base_url: str) -> str:
    parsed = urlsplit(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path == "/v1":
        path = ""
    elif path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _lm_studio_optional_bool(
    mapping: dict[str, Any], key: str, source: str
) -> bool | None:
    if key not in mapping:
        return None
    value = mapping[key]
    if not isinstance(value, bool):
        raise ModelDiscoveryError(
            f"LM Studio {source} returned a non-boolean {key} capability."
        )
    return value


def _lm_studio_context_length(item: dict[str, Any], source: str) -> int | None:
    value = item.get("max_context_length")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelDiscoveryError(
            f"LM Studio {source} returned an invalid max_context_length."
        )
    return value


def _lm_studio_native_v1_models(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ModelDiscoveryError(
            "LM Studio native v1 returned an unsupported model-list response."
        )

    results: list[dict[str, Any]] = []
    for item in payload["models"]:
        if not isinstance(item, dict):
            raise ModelDiscoveryError(
                "LM Studio native v1 returned an invalid model record."
            )
        model_id = item.get("key")
        if not isinstance(model_id, str) or not model_id.strip():
            logger.warning(
                "Skipping LM Studio native v1 model without a key",
                extra={"provider": "lm_studio", "discovery_source": "native_v1"},
            )
            continue
        model_id = model_id.strip()
        if len(model_id) > 255:
            raise ModelDiscoveryError(
                "LM Studio native v1 returned a model key longer than 255 characters."
            )

        model_type = item.get("type")
        capabilities = item.get("capabilities")
        capabilities = capabilities if isinstance(capabilities, dict) else {}
        is_llm = model_type == "llm"
        is_embedding = model_type == "embedding"
        vision = _lm_studio_optional_bool(capabilities, "vision", "native v1")
        tools = _lm_studio_optional_bool(
            capabilities, "trained_for_tool_use", "native v1"
        )
        if vision is not None:
            supports_image_input = vision
        elif is_embedding:
            supports_image_input = False
        else:
            supports_image_input = None
        if not is_llm and not is_embedding:
            logger.warning(
                "LM Studio native v1 returned an unknown model type",
                extra={
                    "provider": "lm_studio",
                    "discovery_source": "native_v1",
                    "model_type": model_type,
                },
            )

        results.append(
            {
                "model_id": model_id,
                "display_name": item.get("display_name") or model_id,
                "source": ModelSource.DISCOVERED,
                "supports_chat": is_llm,
                "supports_image_input": supports_image_input,
                "supports_tools": tools,
                "supports_image_generation": False,
                "max_input_tokens": _lm_studio_context_length(item, "native v1"),
                "metadata": dict(item),
            }
        )
    return results


def _lm_studio_native_v0_models(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ModelDiscoveryError(
            "LM Studio legacy v0 returned an unsupported model-list response."
        )

    results: list[dict[str, Any]] = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise ModelDiscoveryError(
                "LM Studio legacy v0 returned an invalid model record."
            )
        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            logger.warning(
                "Skipping LM Studio legacy v0 model without an id",
                extra={"provider": "lm_studio", "discovery_source": "native_v0"},
            )
            continue
        model_id = model_id.strip()
        if len(model_id) > 255:
            raise ModelDiscoveryError(
                "LM Studio legacy v0 returned a model id longer than 255 characters."
            )
        model_type = item.get("type")
        results.append(
            {
                "model_id": model_id,
                "display_name": item.get("name") or model_id,
                "source": ModelSource.DISCOVERED,
                "supports_chat": model_type in {"llm", "vlm"},
                "supports_image_input": model_type == "vlm",
                "supports_tools": None,
                "supports_image_generation": False,
                "max_input_tokens": _lm_studio_context_length(item, "legacy v0"),
                "metadata": item,
            }
        )
    return results


async def _discover_lm_studio_models(conn: Connection) -> list[dict[str, Any]]:
    base_url = _base_url_or_default(conn)
    if not base_url:
        return []

    server_root = _lm_studio_server_root(base_url)
    native_sources = (
        ("native_v1", f"{server_root}/api/v1/models", _lm_studio_native_v1_models),
        ("native_v0", f"{server_root}/api/v0/models", _lm_studio_native_v0_models),
    )

    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        for source, url, normalize in native_sources:
            response = await client.get(url, headers=_auth_headers(conn))
            if response.status_code in {404, 405}:
                logger.warning(
                    (
                        "LM Studio current discovery endpoint unavailable; "
                        "trying legacy native fallback"
                        if source == "native_v1"
                        else "LM Studio native discovery endpoints unavailable"
                    ),
                    extra={
                        "provider": "lm_studio",
                        "discovery_source": source,
                        "status_code": response.status_code,
                    },
                )
                continue
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise ModelDiscoveryError(
                    f"LM Studio {source} returned invalid JSON."
                ) from exc
            results = normalize(payload)
            _log_lm_studio_discovery(source, results)
            return results

    raise ModelDiscoveryError(
        "LM Studio native model discovery is unavailable. "
        "Upgrade LM Studio to version 0.4 or newer."
    )


def _log_lm_studio_discovery(source: str, models: list[dict[str, Any]]) -> None:
    logger.info(
        "LM Studio model discovery completed",
        extra={
            "provider": "lm_studio",
            "discovery_source": source,
            "models_total": len(models),
            "chat_models": sum(bool(model.get("supports_chat")) for model in models),
            "vision_models": sum(
                bool(model.get("supports_image_input")) for model in models
            ),
            "embedding_models": sum(
                (model.get("metadata") or {}).get("type") in {"embedding", "embeddings"}
                for model in models
            ),
        },
    )


async def _discover_anthropic_models(conn: Connection) -> list[dict[str, Any]]:
    base_url = _base_url_or_default(conn)
    if not base_url:
        return []

    url = f"{base_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        response = await client.get(url, headers=_anthropic_headers(conn))
    response.raise_for_status()

    results: list[dict[str, Any]] = []
    for item in response.json().get("data", []):
        model_id = item.get("id")
        if not model_id:
            continue
        results.append(
            {
                "model_id": model_id,
                "display_name": item.get("display_name") or model_id,
                "source": ModelSource.DISCOVERED,
                **derive_capabilities(conn, model_id, item),
                "metadata": item,
            }
        )
    return results


async def _ollama_tags_then_show(conn: Connection) -> list[dict[str, Any]]:
    if not conn.base_url:
        return []

    base_url = conn.base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{base_url}/api/tags", headers=_auth_headers(conn))
        response.raise_for_status()
        models = response.json().get("models", [])
        results: list[dict[str, Any]] = []
        for item in models:
            model_id = item.get("model") or item.get("name")
            if not model_id:
                continue
            metadata = dict(item)
            with contextlib.suppress(Exception):
                show_response = await client.post(
                    f"{base_url}/api/show",
                    json={"model": model_id},
                    headers=_auth_headers(conn),
                )
                show_response.raise_for_status()
                metadata.update(show_response.json())
            results.append(
                {
                    "model_id": model_id,
                    "display_name": item.get("name") or model_id,
                    "source": ModelSource.DISCOVERED,
                    **derive_capabilities(conn, model_id, metadata),
                    "metadata": metadata,
                }
            )
    return results


async def _openrouter_models(conn: Connection) -> list[dict[str, Any]]:
    base_url = _base_url_or_default(conn) or "https://openrouter.ai/api/v1"
    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models", headers=_auth_headers(conn)
        )
    response.raise_for_status()
    return normalize_openrouter_models(response.json().get("data", []))


async def _requesty_models(conn: Connection) -> list[dict[str, Any]]:
    base_url = _base_url_or_default(conn) or "https://router.requesty.ai/v1"
    async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/models", headers=_auth_headers(conn)
        )
    response.raise_for_status()
    return normalize_requesty_models(response.json().get("data", []))


def _litellm_static_models(conn: Connection) -> list[dict[str, Any]]:
    provider = conn.provider
    prefix = spec_for(provider).litellm_prefix or provider
    results: list[dict[str, Any]] = []
    for model_string, metadata in litellm.model_cost.items():
        if not isinstance(model_string, str) or not model_string.startswith(
            f"{prefix}/"
        ):
            continue
        model_id = model_string.split("/", 1)[1]
        results.append(
            {
                "model_id": model_id,
                "display_name": metadata.get("display_name") or model_id,
                "source": ModelSource.DISCOVERED,
                **_classify_from_litellm(model_string, model_id),
                "metadata": metadata,
            }
        )
    return results


async def _discover_bedrock_models(conn: Connection) -> list[dict[str, Any]]:
    params = (conn.extra or {}).get("litellm_params", {})
    region_name = params.get("aws_region_name")
    if not region_name:
        return []

    def list_models() -> list[dict[str, Any]]:
        import os

        import boto3

        if bearer_token := params.get("aws_bearer_token_bedrock"):
            try:
                os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bearer_token
                client = boto3.client("bedrock", region_name=region_name)
            finally:
                os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
        else:
            client_kwargs: dict[str, str] = {"region_name": region_name}
            if params.get("aws_access_key_id"):
                client_kwargs["aws_access_key_id"] = params["aws_access_key_id"]
            if params.get("aws_secret_access_key"):
                client_kwargs["aws_secret_access_key"] = params["aws_secret_access_key"]
            client = boto3.client("bedrock", **client_kwargs)

        response = client.list_foundation_models()
        results: list[dict[str, Any]] = []
        for item in response.get("modelSummaries", []):
            model_id = item.get("modelId")
            if not model_id:
                continue
            input_modalities = set(item.get("inputModalities") or [])
            output_modalities = set(item.get("outputModalities") or [])
            results.append(
                {
                    "model_id": model_id,
                    "display_name": item.get("modelName") or model_id,
                    "source": ModelSource.DISCOVERED,
                    "supports_chat": "TEXT" in input_modalities
                    and "TEXT" in output_modalities,
                    "supports_image_input": "IMAGE" in input_modalities,
                    "supports_tools": None,
                    "supports_image_generation": "IMAGE" in output_modalities,
                    "max_input_tokens": None,
                    "metadata": item,
                }
            )
        return results

    return await anyio.to_thread.run_sync(list_models)


async def discover_models(conn: Connection) -> list[dict[str, Any]]:
    spec = spec_for(conn.provider)

    try:
        if spec.discovery == "ollama":
            results = await _ollama_tags_then_show(conn)
        elif spec.discovery == "openrouter":
            results = await _openrouter_models(conn)
        elif spec.discovery == "requesty":
            results = await _requesty_models(conn)
        elif spec.discovery == "anthropic_models":
            results = await _discover_anthropic_models(conn)
        elif spec.discovery == "lm_studio_models":
            results = await _discover_lm_studio_models(conn)
        elif spec.discovery == "openai_models":
            results = await _discover_openai_shaped_models(conn, conn.base_url)
        elif spec.discovery == "bedrock_models":
            results = await _discover_bedrock_models(conn)
        elif spec.discovery == "static":
            results = _litellm_static_models(conn)
        else:
            results = []
    except httpx.HTTPError as exc:
        raise ModelDiscoveryError(_discovery_error_message(conn, exc)) from exc

    if not results and spec.discovery not in {"none", "static"}:
        raise ModelDiscoveryError(
            f"No models found at {_base_url_or_default(conn)}. Check that the URL "
            f"points at your {provider_label(conn.provider)} server and that at "
            "least one model is available."
        )

    return results


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
        return _model_test_error(conn, model.model_id, exc)

    model.supports_chat = True
    return VerifyResult("OK", True, "Model test succeeded.")


__all__ = [
    "ModelDiscoveryError",
    "VerifyResult",
    "derive_capabilities",
    "discover_models",
    "test_model",
    "verify_connection",
]
