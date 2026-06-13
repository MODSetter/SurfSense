"""Unit tests for ``ConnectorService.search_crw`` (fastCRW provider).

fastCRW is a Firecrawl-compatible web scraper. ``search_crw`` calls the
``POST /v1/search`` endpoint and maps the ``{success, data: [...]}`` envelope
into SurfSense's ``(result_object, documents)`` tuple. These tests mock the
HTTP layer so no network call is made — mirroring the connector-config pattern
used by the Tavily / Linkup / Baidu providers.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.services.connector_service import ConnectorService

pytestmark = pytest.mark.unit


def _make_service() -> ConnectorService:
    """Build a ConnectorService without touching the database.

    ``search_crw`` only needs the source-id counter/lock and the patched
    ``get_connector_by_type`` helper, so we bypass ``__init__``.
    """
    import asyncio

    svc = ConnectorService.__new__(ConnectorService)
    svc.source_id_counter = 100000
    svc.counter_lock = asyncio.Lock()
    return svc


def _patch_post(monkeypatch, *, json_data=None, exc: Exception | None = None) -> dict:
    """Patch ``httpx.AsyncClient.post`` and capture the call args."""
    captured: dict = {}

    class _FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return json_data

    async def _fake_post(self, url, headers=None, json=None):  # noqa: A002
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        if exc is not None:
            raise exc
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)
    return captured


@pytest.mark.asyncio
async def test_search_crw_no_connector_returns_empty(monkeypatch):
    svc = _make_service()

    async def _no_connector(connector_type, search_space_id):
        return None

    monkeypatch.setattr(svc, "get_connector_by_type", _no_connector)

    result_object, documents = await svc.search_crw("python", search_space_id=1)

    assert result_object["type"] == "CRW_API"
    assert result_object["sources"] == []
    assert documents == []


@pytest.mark.asyncio
async def test_search_crw_maps_results(monkeypatch):
    svc = _make_service()

    connector = SimpleNamespace(config={"CRW_API_KEY": "sk-test"})

    async def _connector(connector_type, search_space_id):
        return connector

    monkeypatch.setattr(svc, "get_connector_by_type", _connector)

    captured = _patch_post(
        monkeypatch,
        json_data={
            "success": True,
            "data": [
                {
                    "title": "Result One",
                    "url": "https://example.com/1",
                    "description": "snippet one",
                    "markdown": "# full markdown one",
                },
                {
                    "title": "Result Two",
                    "url": "https://example.com/2",
                    "description": "snippet two",
                },
            ],
        },
    )

    result_object, documents = await svc.search_crw(
        "python", search_space_id=1, top_k=5
    )

    # Defaults to the managed cloud endpoint with Bearer auth.
    assert captured["url"] == "https://fastcrw.com/api/v1/search"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"] == {"query": "python", "limit": 5}

    assert result_object["type"] == "CRW_API"
    assert len(result_object["sources"]) == 2
    assert len(documents) == 2

    # Full markdown is preferred when present; otherwise the snippet is used.
    assert documents[0]["content"] == "# full markdown one"
    assert documents[1]["content"] == "snippet two"
    assert documents[0]["document"]["document_type"] == "CRW_API"
    assert documents[0]["document"]["metadata"]["url"] == "https://example.com/1"


@pytest.mark.asyncio
async def test_search_crw_self_host_base_url_no_key(monkeypatch):
    svc = _make_service()

    # Self-host: no API key, custom base URL.
    connector = SimpleNamespace(config={"CRW_BASE_URL": "http://localhost:3000/"})

    async def _connector(connector_type, search_space_id):
        return connector

    monkeypatch.setattr(svc, "get_connector_by_type", _connector)

    captured = _patch_post(monkeypatch, json_data={"success": True, "data": []})

    result_object, documents = await svc.search_crw("python", search_space_id=1)

    # Trailing slash trimmed; no Authorization header when key is absent.
    assert captured["url"] == "http://localhost:3000/v1/search"
    assert "Authorization" not in captured["headers"]
    assert result_object["sources"] == []
    assert documents == []


@pytest.mark.asyncio
async def test_search_crw_error_envelope_returns_empty(monkeypatch):
    svc = _make_service()

    connector = SimpleNamespace(config={"CRW_API_KEY": "sk-test"})

    async def _connector(connector_type, search_space_id):
        return connector

    monkeypatch.setattr(svc, "get_connector_by_type", _connector)
    _patch_post(
        monkeypatch,
        json_data={"success": False, "error": "bad request", "error_code": "BAD"},
    )

    result_object, documents = await svc.search_crw("python", search_space_id=1)

    assert result_object["sources"] == []
    assert documents == []


@pytest.mark.asyncio
async def test_search_crw_http_error_returns_empty(monkeypatch):
    svc = _make_service()

    connector = SimpleNamespace(config={"CRW_API_KEY": "sk-test"})

    async def _connector(connector_type, search_space_id):
        return connector

    monkeypatch.setattr(svc, "get_connector_by_type", _connector)
    _patch_post(monkeypatch, exc=httpx.TimeoutException("timed out"))

    result_object, documents = await svc.search_crw("python", search_space_id=1)

    assert result_object["sources"] == []
    assert documents == []
