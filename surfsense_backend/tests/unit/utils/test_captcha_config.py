"""Unit tests for the generic captcha config gate (Phase 3d, Apache-2 layer)."""

import pytest

from app.config import config
from app.utils.captcha import captcha_enabled, get_captcha_config

pytestmark = pytest.mark.unit


class TestCaptchaEnabled:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.setattr(config, "CAPTCHA_SOLVING_ENABLED", False)
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_API_KEY", "key")
        assert captcha_enabled() is False

    def test_flag_on_but_no_key_is_disabled(self, monkeypatch):
        monkeypatch.setattr(config, "CAPTCHA_SOLVING_ENABLED", True)
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_API_KEY", None)
        assert captcha_enabled() is False

    def test_flag_on_with_key_is_enabled(self, monkeypatch):
        monkeypatch.setattr(config, "CAPTCHA_SOLVING_ENABLED", True)
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_API_KEY", "key")
        assert captcha_enabled() is True


class TestGetCaptchaConfig:
    def test_snapshot_reflects_config(self, monkeypatch):
        monkeypatch.setattr(config, "CAPTCHA_SOLVING_ENABLED", True)
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_API_KEY", "key")
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_PROVIDER", "2captcha")
        monkeypatch.setattr(config, "CAPTCHA_MAX_ATTEMPTS_PER_URL", 3)
        monkeypatch.setattr(config, "CAPTCHA_SOLVE_TIMEOUT_S", 90)
        monkeypatch.setattr(config, "CAPTCHA_TYPE_DEFAULT", "hcaptcha")

        cfg = get_captcha_config()
        assert cfg.enabled is True
        assert cfg.solving_site == "2captcha"
        assert cfg.max_attempts_per_url == 3
        assert cfg.timeout_s == 90
        assert cfg.captcha_type_default == "hcaptcha"

    def test_keyless_config_is_not_enabled(self, monkeypatch):
        monkeypatch.setattr(config, "CAPTCHA_SOLVING_ENABLED", True)
        monkeypatch.setattr(config, "CAPTCHA_SOLVER_API_KEY", None)
        assert get_captcha_config().enabled is False
