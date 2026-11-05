"""The trial route's switch: off, today's trial; on, Business's, with the jobs.

Driven over HTTP with Keygen faked at its transport, as the other route tests
are; the mail is built for real and caught at the mailer.
"""

from __future__ import annotations

import pytest

from license.email import deliver
from license.settings import config
from license.tests.billing_harness import SentMail
from license.tests.test_license_routes import FakeKeygen, keygen_store, mailer, post

pytestmark = pytest.mark.unit

__all__ = ["keygen_store", "mailer"]


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch, mailer) -> SentMail:
    """Mail as the real builder renders it: the route's own fake is bypassed."""
    from license import router as license_router
    from license.email.deliver import deliver_licenses

    caught = SentMail()
    monkeypatch.setattr(license_router, "deliver_licenses", deliver_licenses)
    monkeypatch.setattr(deliver, "is_mail_enabled", lambda: True)
    monkeypatch.setattr(deliver, "get_mailer", lambda: caught)
    monkeypatch.setattr(config, "KEYGEN_POLICY_BUSINESS_TRIAL", "policy-business-trial")
    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)
    return caught


def only_license(store: FakeKeygen) -> dict:
    (record,) = store.licenses.values()
    return record


async def test_with_the_switch_off_the_trial_is_todays(
    keygen_store: FakeKeygen, sent: SentMail
) -> None:
    """Off by default, so nothing changes before launch day."""
    assert config.LICENSE_TRIAL_BUSINESS is False

    reply = await post("/license/trial", "new@example.com")

    record = only_license(keygen_store)
    assert reply.status_code == 200
    assert record["policy"] == "policy-trial"
    assert "jobs" not in record["attributes"]["metadata"]
    (mail,) = sent
    assert mail.subject == "Your SurfSense 14-day trial license"


async def test_with_the_switch_on_the_trial_is_businesss(
    keygen_store: FakeKeygen, sent: SentMail, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "LICENSE_TRIAL_BUSINESS", True)

    reply = await post("/license/trial", "new@example.com")

    record = only_license(keygen_store)
    assert reply.status_code == 200
    assert record["policy"] == "policy-business-trial"
    # Still a trial to the app and to the cohort report; the jobs say what it unlocks.
    assert record["attributes"]["metadata"]["plan"] == "trial"
    assert record["attributes"]["metadata"]["jobs"] == "JOB_QUESTIONNAIRE"
    (mail,) = sent
    assert mail.subject == "Your SurfSense Business 14-day trial license"
    assert "security questionnaire" in mail.text_body
    assert "only plugins and priority support stop" not in mail.text_body


async def test_an_earlier_trial_does_not_use_up_the_business_trial(
    keygen_store: FakeKeygen, sent: SentMail, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The earlier trial unlocked only the scrapers; the job is a new thing to try."""
    await post("/license/trial", "new@example.com")
    monkeypatch.setattr(config, "LICENSE_TRIAL_BUSINESS", True)

    business = await post("/license/trial", "new+again@example.com")
    again = await post("/license/trial", "new@example.com")

    assert (business.status_code, again.status_code) == (200, 409)
    assert sorted(r["policy"] for r in keygen_store.licenses.values()) == [
        "policy-business-trial",
        "policy-trial",
    ]


async def test_the_switch_without_its_policy_refuses_before_keygen(
    keygen_store: FakeKeygen, sent: SentMail, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trial on the old policy would spend the address on a trial without the job."""
    monkeypatch.setattr(config, "LICENSE_TRIAL_BUSINESS", True)
    monkeypatch.setattr(config, "KEYGEN_POLICY_BUSINESS_TRIAL", None)

    reply = await post("/license/trial", "new@example.com")

    assert reply.status_code == 503
    assert keygen_store.requests == []
