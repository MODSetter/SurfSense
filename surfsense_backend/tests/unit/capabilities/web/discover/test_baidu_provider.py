"""BaiduProvider maps the Baidu AI Search references to DiscoverHits, env-keyed.

Boundary mocked: httpx.AsyncClient + config key. NOT mocked: reference→hit mapping.
"""

from __future__ import annotations

import pytest

import app.capabilities.web.discover.providers.baidu as baidu_module
from app.capabilities.web.discover.providers.baidu import BaiduProvider
from app.config import config

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Minimal async-context httpx stand-in returning a canned payload."""

    payload: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        return _FakeResponse(type(self).payload)


def _install(monkeypatch, payload):
    monkeypatch.setattr(config, "BAIDU_API_KEY", "k")
    _FakeAsyncClient.payload = payload
    monkeypatch.setattr(baidu_module.httpx, "AsyncClient", _FakeAsyncClient)


def test_is_available_reflects_the_env_key(monkeypatch):
    monkeypatch.setattr(config, "BAIDU_API_KEY", "k")
    assert BaiduProvider().is_available() is True
    monkeypatch.setattr(config, "BAIDU_API_KEY", None)
    assert BaiduProvider().is_available() is False


async def test_maps_references_to_hits(monkeypatch):
    _install(
        monkeypatch,
        {
            "references": [
                {"title": "Acme", "url": "https://acme.cn", "content": "hello"},
                {"title": "No URL", "url": "", "content": "skip"},
            ]
        },
    )

    hits = await BaiduProvider().search("acme", top_k=10)

    assert [h.url for h in hits] == ["https://acme.cn"]
    assert hits[0].title == "Acme"
    assert hits[0].snippet == "hello"
    assert hits[0].provider == "baidu"


async def test_respects_top_k(monkeypatch):
    _install(
        monkeypatch,
        {
            "references": [
                {"title": f"n{i}", "url": f"https://{i}.cn", "content": "c"}
                for i in range(5)
            ]
        },
    )

    hits = await BaiduProvider().search("q", top_k=2)

    assert len(hits) == 2
