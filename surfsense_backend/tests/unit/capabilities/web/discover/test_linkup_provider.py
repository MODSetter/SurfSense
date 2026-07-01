"""LinkupProvider maps the Linkup SDK results to DiscoverHits, env-keyed.

Boundary mocked: the LinkupClient SDK + config key. NOT mocked: result→hit mapping.
"""

from __future__ import annotations

import pytest

import app.capabilities.web.discover.providers.linkup as linkup_module
from app.capabilities.web.discover.providers.linkup import LinkupProvider
from app.config import config

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, name, url, content):
        self.name = name
        self.url = url
        self.content = content
        self.type = "text"


class _Response:
    def __init__(self, results):
        self.results = results


class _FakeClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, *, query, depth, output_type):
        return _Response(
            [
                _Result("Acme", "https://acme.com", "acme home"),
                _Result("No URL", "", "skip"),
            ]
        )


def test_is_available_reflects_the_env_key(monkeypatch):
    monkeypatch.setattr(config, "LINKUP_API_KEY", "k")
    assert LinkupProvider().is_available() is True
    monkeypatch.setattr(config, "LINKUP_API_KEY", None)
    assert LinkupProvider().is_available() is False


async def test_maps_results_to_hits(monkeypatch):
    monkeypatch.setattr(config, "LINKUP_API_KEY", "k")
    monkeypatch.setattr(linkup_module, "LinkupClient", _FakeClient)

    hits = await LinkupProvider().search("acme", top_k=10)

    assert [h.url for h in hits] == ["https://acme.com"]
    assert hits[0].title == "Acme"
    assert hits[0].snippet == "acme home"
    assert hits[0].provider == "linkup"


async def test_respects_top_k(monkeypatch):
    monkeypatch.setattr(config, "LINKUP_API_KEY", "k")

    class _ManyClient(_FakeClient):
        def search(self, *, query, depth, output_type):
            return _Response(
                [_Result(f"n{i}", f"https://{i}.com", "c") for i in range(5)]
            )

    monkeypatch.setattr(linkup_module, "LinkupClient", _ManyClient)

    hits = await LinkupProvider().search("q", top_k=2)

    assert len(hits) == 2
