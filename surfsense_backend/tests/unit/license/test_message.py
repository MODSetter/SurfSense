"""Message rendering. Copy lives on our side of the port, so it is testable."""

from __future__ import annotations

import pytest

from app.license.email.message import ACTIVATION_GUIDE_URL, build_license_email

pytestmark = pytest.mark.unit


def test_single_license_is_attached_under_the_canonical_name():
    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.attachments[0].filename == "surfsense.lic"
    assert message.attachments[0].content == b"CERT"
    assert message.subject == "Your SurfSense license"


def test_multiple_licenses_are_numbered_and_announced():
    """One address can legitimately hold both an individual and a team license."""
    message = build_license_email("resend", to="a@b.test", certificates=("ONE", "TWO"))

    assert [a.filename for a in message.attachments] == [
        "surfsense-1.lic",
        "surfsense-2.lic",
    ]
    assert "2 licenses" in message.text_body
    assert "(2 files)" in message.subject


@pytest.mark.parametrize("kind", ["purchase", "resend", "trial"])
def test_every_kind_renders_a_subject_and_install_steps(kind):
    message = build_license_email(kind, to="a@b.test", certificates=("CERT",))

    assert message.subject
    assert "Settings -> License" in message.text_body
    # The screenshotted version of the same steps. Every kind links it: a
    # resend recipient is the likeliest of the three to be stuck.
    assert ACTIVATION_GUIDE_URL in message.text_body


def test_license_mail_carries_its_own_sender(monkeypatch):
    """The SMTP connection is shared; the From is the feature's own."""
    from app.config import config

    monkeypatch.setattr(config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_FROM", "licenses@surfsense.test")

    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.sender == "licenses@surfsense.test"


def test_license_mail_falls_back_to_the_deployment_sender(monkeypatch):
    from app.config import config

    monkeypatch.setattr(config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_FROM", "")

    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.sender == "noreply@surfsense.test"


def test_trial_mail_carries_the_github_tag_release_and_the_configured_length(
    monkeypatch,
):
    """A trial is handed to an address, so the email has to reach the app too."""
    from app.config import config
    from app.license.release import GITHUB_RELEASE_URL

    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 30)

    message = build_license_email("trial", to="a@b.test", certificates=("CERT",))

    assert GITHUB_RELEASE_URL in message.text_body
    assert "/releases/tag/v" in message.text_body
    assert "/downloads" not in message.text_body
    assert "/releases/latest" not in message.text_body
    assert message.subject == "Your SurfSense 30-day trial license"
    assert "30-day" in message.text_body


def test_installer_assets_are_the_github_tag_download_urls():
    """Same browser_download_url links the /downloads page shows."""
    from app.license.release import ReleaseAsset

    exe = (
        "https://github.com/MODSetter/SurfSense/releases/download/"
        "v2.0.0/SurfSense-Setup-2.0.0.exe"
    )
    dmg = (
        "https://github.com/MODSetter/SurfSense/releases/download/"
        "v2.0.0/SurfSense-2.0.0-arm64.dmg"
    )
    message = build_license_email(
        "trial",
        to="a@b.test",
        certificates=("CERT",),
        installers=(
            ReleaseAsset(name="SurfSense-Setup-2.0.0.exe", url=exe),
            ReleaseAsset(name="SurfSense-2.0.0-arm64.dmg", url=dmg),
        ),
    )

    assert exe in message.text_body
    assert dmg in message.text_body
    assert "Windows (exe):" in message.text_body
    assert "macOS Apple Silicon (dmg):" in message.text_body
    assert "/downloads" not in message.text_body


def test_a_message_with_no_certificate_is_a_programming_error():
    with pytest.raises(ValueError):
        build_license_email("resend", to="a@b.test", certificates=())


def test_idempotency_key_is_carried_through():
    """SMTP ignores it; it exists so an API provider can dedupe retries later."""
    message = build_license_email(
        "trial", to="a@b.test", certificates=("CERT",), idempotency_key="lic_1"
    )

    assert message.idempotency_key == "lic_1"
