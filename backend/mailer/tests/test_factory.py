"""Mail enablement, and the rule that disabled must not look like success."""

from __future__ import annotations

import pytest

from mailer import build_mailer, get_mailer, is_mail_enabled, reset_mailer
from mailer.settings import MailerSettings, config

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_mailer()
    yield
    reset_mailer()


@pytest.fixture
def smtp_configured(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_SECURITY", "starttls")
    monkeypatch.setattr(config, "SMTP_USERNAME", "user")
    return config


def test_mail_is_off_unless_switched_on():
    """SMTP_ENABLED defaults to false, so a fresh deployment sends nothing."""
    assert MailerSettings({}).SMTP_ENABLED is False
    assert MailerSettings({"SMTP_ENABLED": "true"}).SMTP_ENABLED is True


@pytest.mark.parametrize("enabled", [True, False])
def test_enablement_follows_the_flag(monkeypatch, enabled):
    """Routes that exist only to mail something refuse when this is false."""
    monkeypatch.setattr(config, "SMTP_ENABLED", enabled)

    assert is_mail_enabled() is enabled


def test_an_unconfigured_host_fails_loudly(monkeypatch, smtp_configured):
    """Enabled with a typo'd host must raise, never degrade to discarding."""
    monkeypatch.setattr(smtp_configured, "SMTP_HOST", "")

    with pytest.raises(ValueError, match="SMTP_HOST"):
        build_mailer()


def test_a_missing_default_sender_fails_loudly(monkeypatch, smtp_configured):
    """Features may override the From, but a deployment needs a default."""
    monkeypatch.setattr(smtp_configured, "SMTP_FROM", "")

    with pytest.raises(ValueError, match="SMTP_FROM"):
        build_mailer()


def test_instance_is_cached_until_mail_is_toggled(monkeypatch, smtp_configured):
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    first = get_mailer()
    assert get_mailer() is first

    monkeypatch.setattr(config, "SMTP_ENABLED", False)
    assert get_mailer() is not first
