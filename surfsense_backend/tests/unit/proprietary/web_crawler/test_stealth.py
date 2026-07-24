"""Unit tests for the Phase 3e stealth kwargs builder (proprietary boundary)."""

import pytest

from app.config import config
from app.proprietary.web_crawler import stealth
from app.proprietary.web_crawler.stealth import (
    build_stealthy_kwargs,
    get_stealth_config,
    location_to_locale_timezone,
)

pytestmark = pytest.mark.unit


def _set_proxy_location(monkeypatch: pytest.MonkeyPatch, location: str) -> None:
    """Point get_stealth_config at a stub provider with the given exit region."""

    class _StubProvider:
        def get_location(self) -> str:
            return location

    monkeypatch.setattr(stealth, "get_active_provider", lambda: _StubProvider())


class TestLocationToLocaleTimezone:
    def test_alpha2_code(self):
        assert location_to_locale_timezone("us") == ("en-US", "America/New_York")
        assert location_to_locale_timezone("de") == ("de-DE", "Europe/Berlin")

    def test_case_and_whitespace_insensitive(self):
        assert location_to_locale_timezone("  US  ") == (
            "en-US",
            "America/New_York",
        )

    def test_full_country_name_alias(self):
        assert location_to_locale_timezone("Germany") == (
            "de-DE",
            "Europe/Berlin",
        )
        assert location_to_locale_timezone("united kingdom") == (
            "en-GB",
            "Europe/London",
        )

    def test_leading_token_of_vendor_string(self):
        # Vendor strings like "us:nyc" / "de-rotating" still resolve on the head.
        assert location_to_locale_timezone("us:nyc") == (
            "en-US",
            "America/New_York",
        )
        assert location_to_locale_timezone("de-rotating") == (
            "de-DE",
            "Europe/Berlin",
        )

    def test_empty_and_unknown_return_none(self):
        assert location_to_locale_timezone("") == (None, None)
        assert location_to_locale_timezone(None) == (None, None)
        assert location_to_locale_timezone("atlantis") == (None, None)


class TestBuildStealthyKwargs:
    def test_defaults_have_no_geoip_keys(self, monkeypatch):
        # geoip off => locale/timezone_id absent (browser keeps system default).
        monkeypatch.setattr(config, "CRAWL_GEOIP_MATCH_ENABLED", False)
        monkeypatch.setattr(config, "CRAWL_BLOCK_WEBRTC", True)
        monkeypatch.setattr(config, "CRAWL_HIDE_CANVAS", False)
        monkeypatch.setattr(config, "CRAWL_GOOGLE_SEARCH_REFERER", True)
        monkeypatch.setattr(config, "CRAWL_DNS_OVER_HTTPS", False)
        _set_proxy_location(monkeypatch, "us")

        kwargs = build_stealthy_kwargs(get_stealth_config())

        assert kwargs == {
            "block_webrtc": True,
            "hide_canvas": False,
            "google_search": True,
            "dns_over_https": False,
        }
        assert "locale" not in kwargs
        assert "timezone_id" not in kwargs

    def test_flags_reflect_config(self, monkeypatch):
        monkeypatch.setattr(config, "CRAWL_GEOIP_MATCH_ENABLED", False)
        monkeypatch.setattr(config, "CRAWL_BLOCK_WEBRTC", False)
        monkeypatch.setattr(config, "CRAWL_HIDE_CANVAS", True)
        monkeypatch.setattr(config, "CRAWL_GOOGLE_SEARCH_REFERER", False)
        monkeypatch.setattr(config, "CRAWL_DNS_OVER_HTTPS", True)
        _set_proxy_location(monkeypatch, "")

        kwargs = build_stealthy_kwargs(get_stealth_config())

        assert kwargs["block_webrtc"] is False
        assert kwargs["hide_canvas"] is True
        assert kwargs["google_search"] is False
        assert kwargs["dns_over_https"] is True

    def test_geoip_on_adds_locale_timezone(self, monkeypatch):
        monkeypatch.setattr(config, "CRAWL_GEOIP_MATCH_ENABLED", True)
        monkeypatch.setattr(config, "CRAWL_BLOCK_WEBRTC", True)
        monkeypatch.setattr(config, "CRAWL_HIDE_CANVAS", False)
        monkeypatch.setattr(config, "CRAWL_GOOGLE_SEARCH_REFERER", True)
        monkeypatch.setattr(config, "CRAWL_DNS_OVER_HTTPS", False)
        _set_proxy_location(monkeypatch, "de")

        kwargs = build_stealthy_kwargs(get_stealth_config())

        assert kwargs["locale"] == "de-DE"
        assert kwargs["timezone_id"] == "Europe/Berlin"

    def test_geoip_on_but_unknown_location_skips(self, monkeypatch):
        monkeypatch.setattr(config, "CRAWL_GEOIP_MATCH_ENABLED", True)
        monkeypatch.setattr(config, "CRAWL_BLOCK_WEBRTC", True)
        monkeypatch.setattr(config, "CRAWL_HIDE_CANVAS", False)
        monkeypatch.setattr(config, "CRAWL_GOOGLE_SEARCH_REFERER", True)
        monkeypatch.setattr(config, "CRAWL_DNS_OVER_HTTPS", False)
        _set_proxy_location(monkeypatch, "atlantis")

        kwargs = build_stealthy_kwargs(get_stealth_config())

        assert "locale" not in kwargs
        assert "timezone_id" not in kwargs
