"""Transport selection, and the rule that `null` must not look like success."""

from __future__ import annotations

import pytest

from app.config import config
from app.mailer import build_mailer, get_mailer, is_mail_enabled, reset_mailer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_mailer()
    yield
    reset_mailer()


@pytest.mark.parametrize(
    ("transport", "enabled"),
    [("null", False), ("console", True), ("smtp", True)],
)
def test_only_delivering_transports_count_as_enabled(monkeypatch, transport, enabled):
    """`null` accepts and drops, so routes that exist to mail must refuse it."""
    monkeypatch.setattr(config, "LICENSE_MAIL_TRANSPORT", transport)

    assert is_mail_enabled() is enabled


def test_a_vendor_name_is_not_a_transport(monkeypatch):
    """The setting picks how mail is sent, never who sends it.

    Anyone reaching for a company name here has misread the knob, and a typo
    must fail loudly rather than silently discarding license mail.
    """
    monkeypatch.setattr(config, "LICENSE_MAIL_TRANSPORT", "resend")

    with pytest.raises(ValueError, match="Unknown LICENSE_MAIL_TRANSPORT"):
        build_mailer()


def test_null_transport_accepts_and_discards(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_MAIL_TRANSPORT", "null")
    from app.mailer.protocol import LicenseEmail

    mailer = build_mailer()
    message = LicenseEmail(to="a@b.test", kind="trial", subject="s", text_body="t")

    import asyncio

    assert asyncio.run(mailer.send(message)) is None


def test_instance_is_cached_until_the_transport_changes(monkeypatch):
    monkeypatch.setattr(config, "LICENSE_MAIL_TRANSPORT", "null")
    first = get_mailer()
    assert get_mailer() is first

    monkeypatch.setattr(config, "LICENSE_MAIL_TRANSPORT", "console")
    assert get_mailer() is not first
