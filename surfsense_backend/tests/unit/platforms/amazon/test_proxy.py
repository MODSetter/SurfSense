from __future__ import annotations

import pytest

from app.config import Config
from app.utils.proxy.providers.dataimpulse import DataImpulseProvider


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
    assert "token__cr.us__sid.location-123" in first
    assert first.endswith("@gw.dataimpulse.com:823")


def test_dataimpulse_sticky_url_replaces_existing_session(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token__cr.us__sid.old:secret@gw.dataimpulse.com:823",
    )

    result = DataImpulseProvider().get_sticky_proxy_url("new")

    assert "__sid.old" not in result
    assert result.count("__sid.new") == 1


def test_dataimpulse_sticky_url_rewrites_country(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token__cr.us:secret@gw.dataimpulse.com:823",
    )

    result = DataImpulseProvider().get_sticky_proxy_url("new", "gb")

    assert "token__cr.gb__sid.new" in result
    assert "__cr.us" not in result


def test_dataimpulse_sticky_url_rejects_empty_session(monkeypatch):
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://token:secret@gw.dataimpulse.com:823",
    )

    with pytest.raises(ValueError):
        DataImpulseProvider().get_sticky_proxy_url("...")
