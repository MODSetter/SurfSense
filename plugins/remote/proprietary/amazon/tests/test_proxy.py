from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from proprietary.scraping.config import Config
from proprietary.scraping.proxy.providers.dataimpulse import DataImpulseProvider


def test_dataimpulse_sticky_url_is_deterministic(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token__cr.us:secret@gw.dataimpulse.com:823",
    )
    provider = DataImpulseProvider()

    first = provider.get_sticky_proxy_url("location-123")
    second = provider.get_sticky_proxy_url("location-123")

    assert first == second
    parts = urlsplit(first)
    assert parts.username == "token__cr.us"
    assert 10000 <= parts.port <= 20000


def test_dataimpulse_sticky_url_replaces_existing_session(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token__cr.us__sid.old:secret@gw.dataimpulse.com:823",
    )

    result = DataImpulseProvider().get_sticky_proxy_url("new")

    assert "__sid" not in result
    assert 10000 <= urlsplit(result).port <= 20000


def test_dataimpulse_sticky_url_rewrites_country(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token__cr.us:secret@gw.dataimpulse.com:823",
    )

    result = DataImpulseProvider().get_sticky_proxy_url("new", "gb")

    assert urlsplit(result).username == "token__cr.gb"


def test_dataimpulse_sticky_url_rejects_empty_session(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token:secret@gw.dataimpulse.com:823",
    )

    with pytest.raises(ValueError):
        DataImpulseProvider().get_sticky_proxy_url("...")
