"""Live SMTP contract; opt in with SMTP_INTEGRATION=1.

Every other mailer test stubs ``_send_blocking``, so the socket, the SMTP
conversation and the MIME round trip are otherwise never executed -- the code
most likely to be wrong in production is the code with no coverage. This test
sends through the real path and asks the receiving server what arrived.

Run it against the dev-stack Mailpit:

    docker compose -f docker/docker-compose.dev.yml --profile mail up -d mailpit
    SMTP_INTEGRATION=1 pytest tests/integration/mailer

What it still does not cover: STARTTLS negotiation and ``login()`` (Mailpit
here accepts plaintext without credentials), and deliverability -- a verified
From domain and spam placement are answerable only by a real provider.
"""

from __future__ import annotations

import os

import httpx
import pytest

from app.config import config
from app.license.email.message import build_license_email
from app.mailer.smtp import SmtpMailer

pytestmark = pytest.mark.integration

MAILPIT_API = os.getenv("MAILPIT_API_URL", "http://localhost:8025")

pytest.importorskip("httpx")

if os.getenv("SMTP_INTEGRATION") != "1":
    pytest.skip(
        "Live SMTP contract; set SMTP_INTEGRATION=1 with Mailpit running",
        allow_module_level=True,
    )


@pytest.fixture
def mailpit(monkeypatch):
    """Point the sender at Mailpit and hand back a cleared inbox."""
    monkeypatch.setattr(config, "SMTP_ENABLED", True)
    monkeypatch.setattr(config, "SMTP_HOST", os.getenv("SMTP_HOST", "localhost"))
    monkeypatch.setattr(config, "SMTP_PORT", int(os.getenv("SMTP_PORT", "1025")))
    monkeypatch.setattr(config, "SMTP_USERNAME", "")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")
    monkeypatch.setattr(config, "SMTP_SECURITY", "none")
    monkeypatch.setattr(config, "SMTP_TIMEOUT_SECONDS", 10)
    monkeypatch.setattr(config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_FROM", "licenses@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_REPLY_TO", "support@surfsense.test")

    with httpx.Client(base_url=MAILPIT_API, timeout=10.0) as client:
        client.delete("/api/v1/messages")
        yield client


def _latest(client: httpx.Client) -> dict:
    messages = client.get("/api/v1/messages").raise_for_status().json()["messages"]
    assert messages, "Mailpit received nothing"
    return client.get(f"/api/v1/message/{messages[0]['ID']}").raise_for_status().json()


async def test_a_license_email_survives_a_real_smtp_conversation(mailpit):
    """The whole point: this is the only test that opens a socket."""
    certificate = (
        "-----BEGIN LICENSE FILE-----\nCONTRACT-BYTES\n-----END LICENSE FILE-----\n"
    )

    await SmtpMailer().send(
        build_license_email(
            "resend", to="buyer@example.com", certificates=(certificate,)
        )
    )

    message = _latest(mailpit)
    assert message["From"]["Address"] == "licenses@surfsense.test"
    assert [r["Address"] for r in message["To"]] == ["buyer@example.com"]
    assert "resent" in message["Subject"]


async def test_the_license_file_arrives_byte_for_byte(mailpit):
    """Base64 transfer encoding must not mangle the certificate."""
    certificate = (
        "-----BEGIN LICENSE FILE-----\nCONTRACT-BYTES\n-----END LICENSE FILE-----\n"
    )

    await SmtpMailer().send(
        build_license_email(
            "purchase", to="buyer@example.com", certificates=(certificate,)
        )
    )

    message = _latest(mailpit)
    attachment = message["Attachments"][0]
    assert attachment["FileName"] == "surfsense.lic"
    assert attachment["ContentType"] == "application/octet-stream"

    body = (
        mailpit.get(f"/api/v1/message/{message['ID']}/part/{attachment['PartID']}")
        .raise_for_status()
        .text
    )
    assert body == certificate


async def test_the_per_feature_sender_reaches_the_wire(mailpit):
    """Sender travels on the message, so a shared connection stays shared."""
    await SmtpMailer().send(
        build_license_email("trial", to="person@example.com", certificates=("CERT\n",))
    )

    message = _latest(mailpit)
    assert message["From"]["Address"] == "licenses@surfsense.test"
    assert [r["Address"] for r in message["ReplyTo"]] == ["support@surfsense.test"]


async def test_several_licenses_arrive_as_separate_attachments(mailpit):
    """A resend can legitimately carry more than one file."""
    await SmtpMailer().send(
        build_license_email(
            "resend", to="buyer@example.com", certificates=("ONE\n", "TWO\n")
        )
    )

    message = _latest(mailpit)
    assert [a["FileName"] for a in message["Attachments"]] == [
        "surfsense-1.lic",
        "surfsense-2.lic",
    ]
