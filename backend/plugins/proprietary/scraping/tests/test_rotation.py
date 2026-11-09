"""Unit tests for the shared cross-country exit rotation helper.

Offline: the provider is faked via monkeypatch, so no network/proxy is touched.
"""

from __future__ import annotations

from proprietary.scraping.proxy import rotation


class _Prov:
    def __init__(self, location: str) -> None:
        self._location = location

    def get_location(self) -> str:
        return self._location


def test_lead_country_leads_and_dedupes(monkeypatch):
    # The configured/default exit country leads and isn't duplicated in the walk.
    monkeypatch.setattr(rotation, "get_active_provider", lambda: _Prov("gb"))
    countries = rotation.rotation_countries()

    assert countries[0] == "gb"
    assert len(countries) == len(set(countries))  # de-duplicated
    assert set(rotation.FALLBACK_COUNTRIES) <= set(countries)  # fallbacks kept


def test_no_configured_country_uses_fallbacks_only(monkeypatch):
    # A bare PROXY_URL (no country) leaves just the fallback pools, in order.
    monkeypatch.setattr(rotation, "get_active_provider", lambda: _Prov(""))
    assert rotation.rotation_countries() == rotation.FALLBACK_COUNTRIES


def test_walk_covers_every_country_and_wraps(monkeypatch):
    # A whole-pool block can't stall the walk: every country is reached, and the
    # index cycles (wraps) rather than running off the end.
    monkeypatch.setattr(rotation, "get_active_provider", lambda: _Prov("us"))
    countries = rotation.rotation_countries()
    tried = {rotation.country_for_rotation(n) for n in range(len(countries))}

    assert tried == set(countries)
    assert rotation.country_for_rotation(len(countries)) == countries[0]  # wraps
