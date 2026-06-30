"""Unit tests for the Phase 3e block classifier (Apache-2 layer)."""

import pytest

from app.utils.crawl import BlockType, classify_block

pytestmark = pytest.mark.unit


class TestClassifyBlock:
    def test_ok_on_plain_content(self):
        assert classify_block(200, "<html><body>hello</body></html>") is BlockType.OK

    def test_none_body_is_empty(self):
        assert classify_block(200, None) is BlockType.EMPTY
        assert classify_block(200, "   ") is BlockType.EMPTY

    def test_rate_limited_takes_precedence(self):
        # 429 wins even if a challenge marker is present in the body.
        assert (
            classify_block(429, '<div class="cf-turnstile"></div>')
            is BlockType.RATE_LIMITED
        )

    @pytest.mark.parametrize(
        "html",
        [
            "<title>Just a moment...</title>",
            "<h1>Checking your browser before accessing</h1>",
            "please enable javascript and cookies to continue",
            "verify you are human",
            '<div id="challenge-running"></div>',
            '<div id="turnstile-wrapper"></div>',
            '<div class="cf-turnstile"></div>',
            "blocked by ddos-guard.net",
        ],
    )
    def test_cloudflare_markers(self, html):
        assert classify_block(403, html) is BlockType.CLOUDFLARE

    def test_hcaptcha(self):
        assert (
            classify_block(200, '<div class="h-captcha"></div>')
            is BlockType.CAPTCHA_HCAPTCHA
        )

    def test_recaptcha(self):
        assert (
            classify_block(200, '<div class="g-recaptcha"></div>')
            is BlockType.CAPTCHA_RECAPTCHA
        )

    def test_datadome(self):
        assert (
            classify_block(403, "var dd={'host':'geo.captcha-delivery.com'}")
            is BlockType.DATADOME
        )

    def test_kasada(self):
        assert classify_block(200, "window.KPSDK.configure()") is BlockType.KASADA

    def test_bot_gate_status_without_marker_is_unknown(self):
        # 202/403 with no recognized challenge marker => generic blocked-ish.
        assert classify_block(202, "<html><body>x</body></html>") is BlockType.UNKNOWN
        assert classify_block(403, "<html><body>x</body></html>") is BlockType.UNKNOWN

    def test_bot_gate_status_empty_body_is_unknown(self):
        assert classify_block(403, None) is BlockType.UNKNOWN

    def test_cloudflare_marker_beats_generic_403(self):
        # A 403 Cloudflare page is CLOUDFLARE, not UNKNOWN.
        assert (
            classify_block(403, "<title>Just a moment...</title>")
            is BlockType.CLOUDFLARE
        )
