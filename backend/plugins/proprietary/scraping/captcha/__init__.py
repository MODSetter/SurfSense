"""Solving captchas with a vendor, for the scrapers that meet one: Google Search's /sorry wall."""

from proprietary.scraping.captcha.config import (
    CaptchaConfig,
    captcha_enabled,
    get_captcha_config,
)

__all__ = ["CaptchaConfig", "captcha_enabled", "get_captcha_config"]
