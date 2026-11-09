"""Unit tests for the Phase 3e block classifier (Apache-2 layer)."""

import pytest

from proprietary.web_crawl.classifier import (
    CHALLENGE_TYPES,
    BlockType,
    classify_block,
    is_interstitial,
)


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


class TestIsInterstitial:
    """The wall itself, not a widget or tag that also sits on healthy pages."""

    def test_cloudflare_wall(self):
        assert is_interstitial("<title>Just a moment...</title>")
        assert is_interstitial("<p>Verify you are human by completing the action</p>")

    def test_datadome_block_page(self):
        assert is_interstitial('<iframe src="https://geo.captcha-delivery.com/x">')

    def test_widgets_and_tags_on_healthy_pages(self):
        assert not is_interstitial('<div class="cf-turnstile"></div>')
        assert not is_interstitial('<script src="https://js.datadome.co/tags.js">')
        assert not is_interstitial('<div class="g-recaptcha"></div>')
        assert not is_interstitial(None)

    def test_challenge_types_are_the_walls_only_stealth_passes(self):
        assert BlockType.CLOUDFLARE in CHALLENGE_TYPES
        assert BlockType.RATE_LIMITED not in CHALLENGE_TYPES
        assert BlockType.UNKNOWN not in CHALLENGE_TYPES
