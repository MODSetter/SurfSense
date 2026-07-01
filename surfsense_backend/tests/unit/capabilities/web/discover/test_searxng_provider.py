"""SearxngProvider maps the SearXNG service's sources to DiscoverHits.

Boundary mocked: the web_search_service module. NOT mocked: the source→hit mapping.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import app.capabilities.web.discover.providers.searxng as searxng_module
from app.capabilities.web.discover.providers.searxng import SearxngProvider

pytestmark = pytest.mark.unit


def _result(sources):
    return ({"sources": sources}, [])


async def test_maps_sources_to_hits(monkeypatch):
    provider = SearxngProvider()
    monkeypatch.setattr(
        searxng_module.web_search_service,
        "search",
        AsyncMock(
            return_value=_result(
                [
                    {"title": "Acme", "url": "https://acme.com", "description": "home"},
                    {
                        "title": "Docs",
                        "url": "https://acme.com/docs",
                        "description": "",
                    },
                    {"title": "no url", "url": "", "description": "skip me"},
                ]
            )
        ),
    )

    hits = await provider.search("acme", top_k=5)

    assert [h.url for h in hits] == ["https://acme.com", "https://acme.com/docs"]
    assert hits[0].title == "Acme"
    assert hits[0].snippet == "home"
    assert hits[1].snippet is None  # empty description normalizes to None
    assert all(h.provider == "searxng" for h in hits)


def test_is_available_reflects_the_service(monkeypatch):
    provider = SearxngProvider()
    monkeypatch.setattr(searxng_module.web_search_service, "is_available", lambda: True)
    assert provider.is_available() is True
    monkeypatch.setattr(
        searxng_module.web_search_service, "is_available", lambda: False
    )
    assert provider.is_available() is False
