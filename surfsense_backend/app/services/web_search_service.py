"""
Platform-level web search service backed by SearXNG.

Redis is used only for result caching (graceful degradation if unavailable).
The circuit breaker is fully in-process — no external dependency, zero
latency overhead.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import threading
import time
from typing import Any
from urllib.parse import urljoin

import httpx
import redis

from app.config import config

logger = logging.getLogger(__name__)

_EMPTY_RESULT: dict[str, Any] = {
    "id": 11,
    "name": "Web Search",
    "type": "SEARXNG_API",
    "sources": [],
}

# ---------------------------------------------------------------------------
# Redis — used only for result caching
# ---------------------------------------------------------------------------

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


# ---------------------------------------------------------------------------
# In-process Circuit Breaker (no Redis dependency)
# ---------------------------------------------------------------------------

_CB_FAILURE_THRESHOLD = 5
_CB_FAILURE_WINDOW_SECONDS = 60
_CB_COOLDOWN_SECONDS = 30

_cb_lock = threading.Lock()
_cb_failure_count: int = 0
_cb_last_failure_time: float = 0.0
_cb_open_until: float = 0.0


def _circuit_is_open() -> bool:
    return time.monotonic() < _cb_open_until


def _record_failure() -> None:
    global _cb_failure_count, _cb_last_failure_time, _cb_open_until
    now = time.monotonic()
    with _cb_lock:
        if now - _cb_last_failure_time > _CB_FAILURE_WINDOW_SECONDS:
            _cb_failure_count = 0
        _cb_failure_count += 1
        _cb_last_failure_time = now
        if _cb_failure_count >= _CB_FAILURE_THRESHOLD:
            _cb_open_until = now + _CB_COOLDOWN_SECONDS
            logger.warning(
                "Circuit breaker OPENED after %d failures — "
                "SearXNG calls paused for %ds",
                _cb_failure_count,
                _CB_COOLDOWN_SECONDS,
            )


def _record_success() -> None:
    global _cb_failure_count, _cb_open_until
    with _cb_lock:
        _cb_failure_count = 0
        _cb_open_until = 0.0


# ---------------------------------------------------------------------------
# Result Caching (Redis, graceful degradation)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_PREFIX = "websearch:cache:"


def _cache_key(query: str, engines: str | None, language: str | None) -> str:
    raw = f"{query}|{engines or ''}|{language or ''}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"{_CACHE_PREFIX}{digest}"


def _cache_get(key: str) -> dict | None:
    try:
        data = _get_redis().get(key)
        if data:
            return json.loads(data)
    except (redis.RedisError, json.JSONDecodeError):
        pass
    return None


def _cache_set(key: str, value: dict) -> None:
    with contextlib.suppress(redis.RedisError):
        _get_redis().setex(key, _CACHE_TTL_SECONDS, json.dumps(value))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return ``True`` when the platform SearXNG host is configured."""
    return bool(config.SEARXNG_DEFAULT_HOST)


async def health_check() -> dict[str, Any]:
    """Ping the SearXNG ``/healthz`` endpoint and return status info."""
    host = config.SEARXNG_DEFAULT_HOST
    if not host:
        return {"status": "unavailable", "error": "SEARXNG_DEFAULT_HOST not set"}

    healthz_url = urljoin(host if host.endswith("/") else f"{host}/", "healthz")
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            resp = await client.get(healthz_url)
            resp.raise_for_status()
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "status": "healthy",
            "response_time_ms": elapsed_ms,
            "circuit_breaker": "open" if _circuit_is_open() else "closed",
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        return {
            "status": "unhealthy",
            "error": str(exc),
            "response_time_ms": elapsed_ms,
            "circuit_breaker": "open" if _circuit_is_open() else "closed",
        }


async def search(
    query: str,
    top_k: int = 20,
    *,
    engines: str | None = None,
    language: str | None = None,
    safesearch: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute a web search against the platform SearXNG instance.

    Returns the standard ``(result_object, documents)`` tuple expected by
    ``ConnectorService.search_searxng``.
    """
    host = config.SEARXNG_DEFAULT_HOST
    if not host:
        return dict(_EMPTY_RESULT), []

    if _circuit_is_open():
        logger.info("Web search skipped — circuit breaker is open")
        result = dict(_EMPTY_RESULT)
        result["error"] = "Web search temporarily unavailable (circuit open)"
        result["status"] = "degraded"
        return result, []

    ck = _cache_key(query, engines, language)
    cached = _cache_get(ck)
    if cached is not None:
        logger.debug("Web search cache HIT for query=%r", query[:60])
        return cached["result"], cached["documents"]

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "limit": max(1, min(top_k, 50)),
    }
    if engines:
        params["engines"] = engines
    if language:
        params["language"] = language
    if safesearch is not None and 0 <= safesearch <= 2:
        params["safesearch"] = safesearch

    searx_endpoint = urljoin(host if host.endswith("/") else f"{host}/", "search")
    headers = {"Accept": "application/json"}

    data: dict[str, Any] | None = None
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
                response = await client.get(
                    searx_endpoint,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
            data = response.json()
            break
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt == 0 and (
                isinstance(exc, httpx.TimeoutException)
                or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code >= 500
                )
            ):
                continue
            break
        except httpx.HTTPError as exc:
            last_error = exc
            break
        except ValueError as exc:
            last_error = exc
            break

    if data is None:
        _record_failure()
        logger.warning("Web search failed after retries: %s", last_error)
        return dict(_EMPTY_RESULT), []

    _record_success()

    searx_results = data.get("results", [])
    if not searx_results:
        return dict(_EMPTY_RESULT), []

    sources_list: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []

    for idx, result in enumerate(searx_results):
        source_id = 200_000 + idx
        description = result.get("content") or result.get("snippet") or ""

        sources_list.append(
            {
                "id": source_id,
                "title": result.get("title", "Web Search Result"),
                "description": description,
                "url": result.get("url", ""),
            }
        )

        documents.append(
            {
                "chunk_id": source_id,
                "content": description or result.get("content", ""),
                "score": result.get("score", 0.0),
                "document": {
                    "id": source_id,
                    "title": result.get("title", "Web Search Result"),
                    "document_type": "SEARXNG_API",
                    "metadata": {
                        "url": result.get("url", ""),
                        "engines": result.get("engines", []),
                        "category": result.get("category"),
                        "source": "SEARXNG_API",
                    },
                },
            }
        )

    result_object: dict[str, Any] = {
        "id": 11,
        "name": "Web Search",
        "type": "SEARXNG_API",
        "sources": sources_list,
    }

    _cache_set(ck, {"result": result_object, "documents": documents})

    return result_object, documents
