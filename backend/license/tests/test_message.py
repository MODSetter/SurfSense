"""Message rendering. Copy lives on our side of the port, so it is testable."""

from __future__ import annotations

from datetime import date

import pytest

from license.email.message import ACTIVATION_GUIDE_URL, build_license_email

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
    from license.settings import config
    from mailer.settings import config as mail_config

    monkeypatch.setattr(mail_config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_FROM", "licenses@surfsense.test")

    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.sender == "licenses@surfsense.test"


def test_license_mail_falls_back_to_the_deployment_sender(monkeypatch):
    from license.settings import config
    from mailer.settings import config as mail_config

    monkeypatch.setattr(mail_config, "SMTP_FROM", "noreply@surfsense.test")
    monkeypatch.setattr(config, "SMTP_LICENSE_FROM", "")

    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.sender == "noreply@surfsense.test"


def test_trial_mail_carries_the_pinned_installers_and_the_configured_length(
    monkeypatch,
):
    """A trial is handed to an address, so the email has to reach the app too."""
    from license.release import APP_RELEASE_TAG
    from license.settings import config

    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)

    message = build_license_email("trial", to="a@b.test", certificates=("CERT",))

    assert f"v={APP_RELEASE_TAG}" in message.text_body
    assert "/releases/latest" not in message.text_body
    assert message.subject == "Your SurfSense 14-day trial license"
    assert "14-day" in message.text_body


@pytest.mark.parametrize("kind", ["purchase", "resend", "trial"])
def test_installers_go_through_the_counting_redirect(kind):
    """Each platform's link is the site redirect, labelled like the /downloads grid."""
    from license.release import installer_links

    message = build_license_email(kind, to="a@b.test", certificates=("CERT",))

    for link in installer_links():
        assert f"{link.label}: {link.url}" in message.text_body
    assert "src=email" in message.text_body
    assert "github.com" not in message.text_body


def test_a_message_with_no_certificate_is_a_programming_error():
    with pytest.raises(ValueError):
        build_license_email("resend", to="a@b.test", certificates=())


def test_idempotency_key_is_carried_through():
    """SMTP ignores it; it exists so an API provider can dedupe retries later."""
    message = build_license_email(
        "trial", to="a@b.test", certificates=("CERT",), idempotency_key="lic_1"
    )

    assert message.idempotency_key == "lic_1"


# Business ---------------------------------------------------------------------

INDIVIDUAL_PROMISES = (
    "works on every machine",
    "only when you choose Check for renewal",
)


def business(**fields):
    from license.email.message import BusinessCopy

    return BusinessCopy(**fields)


@pytest.mark.parametrize(
    "kind", ["purchase", "resend", "trial", "renewal", "conversion"]
)
def test_no_business_mail_makes_the_individual_promises(kind):
    """The app reaches the license server by itself for a Business license's jobs and its
    renewed file, and Business counts people, not machines."""
    term = {"renews_on": date(2027, 10, 26)} if kind == "conversion" else {}
    message = build_license_email(
        kind,
        to="a@b.test",
        certificates=("CERT",),
        business=business(people=4, **term),
    )

    for promise in INDIVIDUAL_PROMISES:
        assert promise not in message.text_body
    assert "Settings -> License" in message.text_body


def test_the_business_purchase_names_the_firm_the_people_and_the_portal(monkeypatch):
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "https://portal.test/p")

    message = build_license_email(
        "purchase",
        to="a@b.test",
        certificates=("CERT",),
        business=business(firm="Acme LLP", people=4, paid=True),
    )

    assert message.subject == "Your SurfSense Business license"
    assert "SurfSense Business for Acme LLP" in message.text_body
    assert "It covers 4 people" in message.text_body
    assert "renews automatically every year" in message.text_body
    assert "https://portal.test/p" in message.text_body


def test_a_solo_purchase_says_one_person():
    message = build_license_email(
        "purchase", to="a@b.test", certificates=("CERT",), business=business(people=1)
    )

    assert "It covers one person." in message.text_body
    assert "Share the file" not in message.text_body


def test_without_a_portal_link_the_business_mail_says_to_reply(monkeypatch):
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "")

    message = build_license_email(
        "renewal", to="a@b.test", certificates=("CERT",), business=business(paid=True)
    )

    assert "reply to this email" in message.text_body


def test_the_business_trial_says_what_stops_and_names_no_portal(monkeypatch):
    from license.settings import config

    monkeypatch.setattr(config, "LICENSE_TRIAL_DAYS", 14)
    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "https://portal.test/p")

    message = build_license_email(
        "trial", to="a@b.test", certificates=("CERT",), business=business()
    )

    assert message.subject == "Your SurfSense Business 14-day trial license"
    assert "only new job runs stop" in message.text_body
    assert "https://portal.test/p" not in message.text_body


def test_only_a_paid_business_license_resent_names_the_portal(monkeypatch):
    """Resend takes a trial's copy when the address holds no paid license, and a trial
    has no subscription to change or cancel."""
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "https://portal.test/p")

    def resent(copy):
        return build_license_email(
            "resend", to="a@b.test", certificates=("CERT",), business=copy
        ).text_body

    trial, paid = resent(business()), resent(business(people=4, paid=True))

    assert "https://portal.test/p" not in trial
    assert "to cancel" not in trial
    assert "https://portal.test/p" in paid


@pytest.mark.parametrize("kind", ["purchase", "trial", "conversion"])
def test_a_business_purchase_trial_or_conversion_ends_with_the_first_job(kind):
    """The license is for jobs, so its first mail goes on to one, in the app's own labels.

    A converted Individual buyer has the app, but has never run a job, and was told
    the app never contacts a license server, so the Allow step is new to them too.
    """
    term = {"renews_on": date(2027, 10, 26)} if kind == "conversion" else {}
    body = build_license_email(
        kind,
        to="a@b.test",
        certificates=("CERT",),
        business=business(people=4, **term),
    ).text_body

    for words in (
        "5. Run your first job.",
        "choose Allow",
        "click Jobs in the left sidebar",
        "press Run beside Security questionnaire",
    ):
        assert words in body
    assert (
        body.index("4. Drop the file in")
        < body.index("5. Run your first job")
        < body.index(ACTIVATION_GUIDE_URL)
    )


@pytest.mark.parametrize(
    ("kind", "plan"),
    [
        ("purchase", None),
        ("trial", None),
        ("resend", None),
        ("renewal", None),
        ("resend", business(people=4)),
        ("renewal", business(people=4)),
    ],
)
def test_no_other_mail_has_a_first_job_step(kind, plan):
    """A resend or a renewal reaches someone already set up; Individual has no jobs."""
    message = build_license_email(
        kind, to="a@b.test", certificates=("CERT",), business=plan
    )

    assert "Run your first job" not in message.text_body
    assert "4. Drop the file in" in message.text_body


def test_the_individual_purchase_mail_says_when_the_key_leaves():
    """The Jobs screen offers an Individual license Check for renewal, which sends its key
    to the license server, so the mail says the key leaves only then."""
    message = build_license_email("purchase", to="a@b.test", certificates=("CERT",))

    assert message.text_body.startswith(
        "Thanks for buying SurfSense. Your license file is attached.\n\n"
        "The file is verified offline and works on every machine you install "
        "SurfSense on. The app sends your license key to SurfSense's license server "
        "only when you choose Check for renewal.\n\n"
    )
    for promise in INDIVIDUAL_PROMISES:
        assert promise in message.text_body
    assert "never contacts a license server" not in message.text_body


def test_an_individual_renewal_asks_for_the_file_to_be_imported():
    """The app does not fetch it yet, so the mail is how the renewal arrives."""
    message = build_license_email("renewal", to="a@b.test", certificates=("CERT",))

    assert message.subject == "Your SurfSense license has renewed"
    assert "replaces the old file" in message.text_body
    assert "Business" not in message.text_body


# conversion -------------------------------------------------------------------


RENEWS_ON = date(2027, 10, 26)


def converted(**fields):
    term = fields if fields else {"renews_on": RENEWS_ON}
    return build_license_email(
        "conversion",
        to="a@b.test",
        certificates=("CERT",),
        business=business(people=1, paid=True, **term),
    )


def test_the_conversion_notice_says_what_changed_and_what_stays(monkeypatch):
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "https://portal.test/p")

    message = converted()

    assert message.subject == "Your SurfSense license is now Business Solo"
    assert message.attachments[0].filename == "surfsense.lic"
    assert message.attachments[0].content == b"CERT"
    body = message.text_body
    for words in (
        "Your SurfSense Individual license is now Business Solo, the Business "
        "license for one person, on the same key.",
        "The attached file replaces the old one: import it in Settings -> License "
        "on each computer you use SurfSense on, or choose Check for renewal on the "
        "Jobs screen, which fetches it.",
        "Business unlocks SurfSense's job plugins, starting with the security "
        "questionnaire.",
        "The scraper plugins your Individual license included have retired; reading "
        "web pages, YouTube and web search are now built into SurfSense, free.",
        # Its buyer may never have read that it renews: the notice names the day.
        "Your purchase is a yearly subscription: it renews automatically on 26 "
        "October 2027, and every year after, at the price you paid, on the same key, "
        "until you cancel.",
        "use the billing portal: https://portal.test/p",
    ):
        assert words in body
    # The steps to import it follow, as in every license mail.
    assert body.index("until you cancel") < body.index("1. Install SurfSense")
    assert ACTIVATION_GUIDE_URL in body


def test_the_conversion_notice_names_no_price_and_no_reminder():
    """The price is whatever Stripe charges, and nothing sends a reminder yet."""
    body = converted().text_body

    assert "$" not in body
    assert "remind" not in body.lower()


def test_a_conversion_notice_for_a_license_that_has_ended_says_when_and_nothing_more(
    monkeypatch,
):
    """Cancelled or paid once: no renewal to promise, nothing to change or keep."""
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "https://portal.test/p")

    body = converted(ends_on=date(2027, 11, 29)).text_body

    assert (
        "It ends on 29 November 2027 and does not renew. After that, SurfSense keeps "
        "working and everything you made stays readable; only new job runs stop."
    ) in body
    assert "renews automatically" not in body
    assert "billing portal" not in body
    assert "reply to this email" not in body
    assert "is now Business Solo, the Business license for one person" in body


@pytest.mark.parametrize(
    ("portal", "said"),
    [
        (
            "https://portal.test/p",
            "To keep it, renew it in the billing portal before 30 October 2027: "
            "https://portal.test/p",
        ),
        ("", "To keep it, reply to this email before 30 October 2027."),
    ],
)
def test_a_conversion_notice_for_one_set_to_cancel_says_how_to_keep_it(
    monkeypatch, portal, said
):
    """Stripe's portal lets a buyer renew a subscription set to cancel until its period
    ends, which comes before the license's last day of grace: the line names it."""
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", portal)

    body = converted(
        ends_on=date(2027, 11, 29), resumable_until=date(2027, 10, 30)
    ).text_body

    assert "It ends on 29 November 2027 and does not renew." in body
    assert said in body
    assert "before then" not in body
    assert "To add or remove people" not in body


def test_without_a_portal_the_conversion_notice_says_to_reply(monkeypatch):
    from license.settings import config

    monkeypatch.setattr(config, "STRIPE_CUSTOMER_PORTAL_URL", "")

    assert "or to cancel, reply to this email." in converted().text_body


def test_the_conversion_notice_has_no_individual_copy():
    """It tells an Individual buyer their license is now Business; there is nothing else to say."""
    with pytest.raises(ValueError, match="only the Business copy"):
        build_license_email("conversion", to="a@b.test", certificates=("CERT",))


def test_a_conversion_notice_names_the_day_it_renews_or_ends():
    """Without either it would promise nothing true about what Stripe does next."""
    with pytest.raises(ValueError, match="renews or ends"):
        build_license_email(
            "conversion",
            to="a@b.test",
            certificates=("CERT",),
            business=business(people=1, paid=True),
        )


def test_a_business_copy_is_only_for_licenses_that_unlock_jobs():
    from license.email.message import BusinessCopy
    from license.models import IssuedLicense

    def issued(plan, jobs=(), max_users=None):
        return IssuedLicense("lic", "CERT", plan, "a@b.test", max_users, "Acme", jobs)

    assert BusinessCopy.of(issued("individual")) is None
    assert BusinessCopy.of(issued("trial")) is None
    assert BusinessCopy.of(issued("trial", ("JOB_QUESTIONNAIRE",))) == BusinessCopy(
        firm="Acme", people=None
    )
    assert BusinessCopy.of(issued("business", ("JOB_QUESTIONNAIRE",), 3)) == (
        BusinessCopy(firm="Acme", people=3, paid=True)
    )
