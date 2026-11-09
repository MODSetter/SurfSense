"""The solver is on only with a key, so no deployment pays for a solve it did not set up."""

import pytest

from proprietary.scraping.captcha import captcha_enabled, get_captcha_config
from proprietary.scraping.config import Config


def test_off_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "CAPTCHA_API_KEY", None)
    assert captcha_enabled() is False


def test_on_with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "CAPTCHA_API_KEY", "key")
    monkeypatch.setattr(Config, "CAPTCHA_PROVIDER", "2captcha")

    assert captcha_enabled() is True
    config = get_captcha_config()
    assert (config.provider, config.api_key) == ("2captcha", "key")
