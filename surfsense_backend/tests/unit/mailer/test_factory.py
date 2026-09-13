"""Mail enablement, and the rule that disabled must not look like success."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.config import config
from app.mailer import build_mailer, get_mailer, is_mail_enabled, reset_mailer

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
    """SMTP_ENABLED must default to false, so a fresh deployment sends nothing.

    This reads the declaration rather than ``config.SMTP_ENABLED`` because the
    runtime value cannot be tested honestly in-process: ``Config`` evaluates its
    class body once at import, ``app/config/__init__.py`` calls ``load_dotenv``
    so a developer's own .env would decide the answer, and reloading the module
    swaps the singleton out from under every module holding a reference to it.
    A subprocess with a clean environment is correct but takes ~15s.

    What matters is that nobody flips the default to TRUE, and that is exactly
    what this catches.
    """
    tree = ast.parse(Path("app/config/__init__.py").read_text())
    defaults = {
        node.targets[0].id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert "SMTP_ENABLED" in defaults, "SMTP_ENABLED is no longer declared"

    getenv_calls = [
        call
        for call in ast.walk(defaults["SMTP_ENABLED"])
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "getenv"
    ]
    assert len(getenv_calls) == 1, "expected one os.getenv in the declaration"
    name, default = getenv_calls[0].args
    assert name.value == "SMTP_ENABLED"
    assert default.value.upper() == "FALSE"


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
