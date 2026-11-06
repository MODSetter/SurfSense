"""Subjects, bodies and sender identity for the license emails.

Copy lives on our side of the port, never in a transport and never hosted at
a vendor. That is what keeps switching provider from becoming a copy
migration.

This module also owns *who license mail comes from*. The SMTP connection is
shared across the backend, so each feature stamps its own address on the
messages it builds instead of the sender object carrying one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from license.models import IssuedLicense
from license.release import InstallerLink, installer_links
from license.settings import config
from mailer.protocol import Attachment, OutboundEmail
from mailer.settings import config as mail_config

LicenseEmailKind = Literal["purchase", "resend", "trial", "renewal", "conversion"]

LICENSE_FILENAME = "surfsense.lic"

# The same steps below, with screenshots of each one. Plain text cannot show
# where the gear is, so the mail carries both: the four lines for a reader who
# wants no detour, and the page for one who is stuck on a step.
ACTIVATION_GUIDE_URL = "https://www.surfsense.com/license/activate"

# Business purchase, trial and conversion: the license is for jobs, so the steps go on to one.
# It names the app's labels as they read: Allow, Sources, Jobs, Run, Security questionnaire.
_FIRST_JOB_STEP = (
    "5. Run your first job. When SurfSense asks to reach its license server, choose Allow, "
    "and it downloads the job.\n"
    "   Then upload a questionnaire (.xlsx) and your policies to Sources, click Jobs in the "
    "left sidebar, and press Run beside Security questionnaire.\n"
)
_FIRST_JOB_KINDS: frozenset[LicenseEmailKind] = frozenset(
    {"purchase", "trial", "conversion"}
)


@dataclass(frozen=True, slots=True)
class BusinessCopy:
    """Business mail, for a Business license or trial: the firm and its people when known.

    Its own words, because the Individual promises do not hold for it: the app
    fetches a renewed file, and the license counts people, not machines.
    """

    firm: str | None = None
    people: int | None = None
    # A paid license has a subscription to change or cancel; a trial has none.
    paid: bool = False
    # A converted license that renews: the day it next does.
    renews_on: date | None = None
    # A converted license that does not renew: the day it ends.
    ends_on: date | None = None
    # Set to cancel: its period's end, until which Stripe's portal lets its buyer
    # renew it. Not ``ends_on``, which adds Business's 30 days of grace.
    resumable_until: date | None = None

    @classmethod
    def of(cls, issued: IssuedLicense) -> BusinessCopy | None:
        """For a license that unlocks the jobs; ``None`` keeps the copy as it was."""
        if issued.plan != "business" and not issued.jobs:
            return None
        paid = issued.plan == "business"
        people = issued.max_users if paid else None
        return cls(firm=issued.firm, people=people, paid=paid)


def _install_steps(
    installers: tuple[InstallerLink, ...], *, first_job: bool = False
) -> str:
    """Steps from nothing to a working license, and with `first_job` to a job run.

    The download comes first because the recipient may not have the app yet:
    a trial is handed out to an address, not to an installation. The links go
    through the site's download redirect, pinned to this release's tag, so an
    old mail keeps naming the build it was sent for.
    """
    links = "\n".join(f"   {link.label}: {link.url}" for link in installers)
    return (
        f"1. Install SurfSense:\n{links}\n"
        + "2. Save the attached surfsense.lic somewhere you can find it.\n"
        + "3. Open SurfSense and go to Settings -> License.\n"
        + "4. Drop the file in, or paste its contents.\n"
        + (_FIRST_JOB_STEP if first_job else "")
        + f"\nStuck on a step? The same guide with screenshots: {ACTIVATION_GUIDE_URL}\n"
    )


_SUBJECTS: dict[LicenseEmailKind, str] = {
    "purchase": "Your SurfSense license",
    "resend": "Your SurfSense license (resent)",
    "trial": "Your SurfSense {days}-day trial license",
    "renewal": "Your SurfSense license has renewed",
}

_INTROS: dict[LicenseEmailKind, str] = {
    "purchase": (
        "Thanks for buying SurfSense. Your license file is attached.\n\n"
        "The file is verified offline and works on every machine you install "
        "SurfSense on. The app sends your license key to SurfSense's license "
        "server only when you choose Check for renewal."
    ),
    "resend": (
        "Here is the SurfSense license file registered to this address.\n\n"
        "If you did not ask for this, you can ignore this email. Nothing about "
        "your license has changed."
    ),
    "trial": (
        "Your {days}-day SurfSense trial license is attached.\n\n"
        "When it expires the app keeps working and your data stays put -- only "
        "plugins and priority support stop."
    ),
    "renewal": (
        "Your SurfSense license has renewed, and the renewed file is attached.\n\n"
        "Import it in Settings -> License on each computer you use SurfSense on; "
        "it replaces the old file."
    ),
}

_BUSINESS_SUBJECTS: dict[LicenseEmailKind, str] = {
    "purchase": "Your SurfSense Business license",
    "resend": "Your SurfSense license (resent)",
    "trial": "Your SurfSense Business {days}-day trial license",
    "renewal": "Your SurfSense Business license has renewed",
    "conversion": "Your SurfSense license is now Business Solo",
}

_BUSINESS_INTROS: dict[LicenseEmailKind, str] = {
    "purchase": (
        "Thanks for choosing SurfSense Business{for_firm}. Your license file is "
        "attached.\n\n"
        "{covers}\n\n"
        "The license renews automatically every year on the same key until you "
        "cancel. When it renews, we email you the renewed file, and SurfSense "
        "can fetch it by itself if you allow it to go online."
    ),
    "resend": (
        "Here is the SurfSense license file registered to this address.\n\n"
        "If you did not ask for this, you can ignore this email. Nothing about "
        "your license has changed."
    ),
    "trial": (
        "Your {days}-day SurfSense Business trial license is attached. It "
        "unlocks the job plugins, starting with the security questionnaire.\n\n"
        "When it expires, SurfSense keeps working and everything you made stays "
        "readable; only new job runs stop."
    ),
    "renewal": (
        "Your SurfSense Business license{for_firm} has renewed, and the renewed "
        "file is attached.\n\n"
        "SurfSense fetches the renewed file by itself on computers you allow to "
        "go online. On a computer that stays offline, import this file in "
        "Settings -> License; it replaces the old one."
    ),
    # Sent once, when an Individual license already sold becomes Business Solo
    # (ADR 0080); its subscription is left as it was bought.
    "conversion": (
        "Your SurfSense Individual license is now Business Solo, the Business "
        "license for one person, on the same key.\n\n"
        "The attached file replaces the old one: import it in Settings -> "
        "License on each computer you use SurfSense on, or choose Check for "
        "renewal on the Jobs screen, which fetches it.\n\n"
        "Business unlocks SurfSense's job plugins, starting with the security "
        "questionnaire. The scraper plugins your Individual license included "
        "have retired; reading web pages, YouTube and web search are now built "
        "into SurfSense, free.\n\n"
        "{term}"
    ),
}


def _term(business: BusinessCopy) -> str:
    """When a converted license renews or ends: Stripe's subscription decides.

    The renewing one names its day, since its buyer may never have read that it
    renews at all.
    """
    if business.renews_on is not None:
        return (
            "Your purchase is a yearly subscription: it renews automatically on "
            f"{_long_day(business.renews_on)}, and every year after, at the price "
            "you paid, on the same key, until you cancel."
        )
    if business.ends_on is not None:
        return (
            f"It ends on {_long_day(business.ends_on)} and does not renew. After "
            "that, SurfSense keeps working and everything you made stays readable; "
            "only new job runs stop."
        )
    raise ValueError("A conversion notice names the day the license renews or ends")


def _long_day(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


def _manage_line() -> str:
    """How a firm changes its people or cancels, with no SurfSense account."""
    portal = config.STRIPE_CUSTOMER_PORTAL_URL
    if portal:
        return (
            f"To add or remove people, or to cancel, use the billing portal: {portal}"
        )
    return "To add or remove people, or to cancel, reply to this email."


def _resume_line(until: date) -> str:
    """How a buyer whose subscription is set to cancel keeps the license, and by when."""
    portal = config.STRIPE_CUSTOMER_PORTAL_URL
    if portal:
        return (
            f"To keep it, renew it in the billing portal before {_long_day(until)}: "
            f"{portal}"
        )
    return f"To keep it, reply to this email before {_long_day(until)}."


def _closing_line(business: BusinessCopy) -> str | None:
    """What a paid license's holder can change; nothing for one that has ended."""
    if not business.paid:
        return None
    if business.ends_on is None:
        return _manage_line()
    if business.resumable_until is None:
        return None
    return _resume_line(business.resumable_until)


def _business_intro(kind: LicenseEmailKind, business: BusinessCopy, days: int) -> str:
    people = business.people or 1
    covers = (
        "It covers one person."
        if people == 1
        else f"It covers {people} people. Share the file with them: each person "
        "imports it on their own computer."
    )
    intro = _BUSINESS_INTROS[kind].format(
        days=days,
        for_firm=f" for {business.firm}" if business.firm else "",
        covers=covers,
        term=_term(business) if kind == "conversion" else "",
    )
    closing = _closing_line(business)
    return f"{intro}\n\n{closing}" if closing else intro


def build_license_email(
    kind: LicenseEmailKind,
    *,
    to: str,
    certificates: tuple[str, ...],
    business: BusinessCopy | None = None,
    idempotency_key: str | None = None,
) -> OutboundEmail:
    """Render one message carrying every certificate issued to ``to``.

    A resend can legitimately carry more than one file (an individual license
    and a team license bought with the same address), so attachments are
    numbered once there is more than one. ``business`` picks the Business
    copy; a resend takes it when any of its files is a Business license.
    """
    if not certificates:
        raise ValueError("A license email needs at least one certificate")

    attachments = tuple(
        Attachment(
            filename=(
                LICENSE_FILENAME if len(certificates) == 1 else f"surfsense-{index}.lic"
            ),
            content=certificate.encode("utf-8"),
        )
        for index, certificate in enumerate(certificates, start=1)
    )

    days = config.LICENSE_TRIAL_DAYS
    if business is None and kind not in _SUBJECTS:
        raise ValueError(f"A {kind} mail has only the Business copy")
    if business is None:
        subject = _SUBJECTS[kind].format(days=days)
        intro = _INTROS[kind].format(days=days)
    else:
        subject = _BUSINESS_SUBJECTS[kind].format(days=days)
        intro = _business_intro(kind, business, days)
    steps = _install_steps(
        installer_links(),
        first_job=business is not None and kind in _FIRST_JOB_KINDS,
    )

    plural = "" if len(certificates) == 1 else f" ({len(certificates)} files)"
    body = f"{intro}\n\n{steps}\n"
    if plural:
        body = (
            f"{intro}\n\n"
            f"{len(certificates)} licenses are registered to this address; all "
            "are attached. Import the one for the plan you want to use.\n\n"
            f"{steps}\n"
        )

    return OutboundEmail(
        to=to,
        subject=subject + plural,
        text_body=body,
        sender=config.SMTP_LICENSE_FROM or mail_config.SMTP_FROM or None,
        reply_to=config.SMTP_LICENSE_REPLY_TO or None,
        attachments=attachments,
        idempotency_key=idempotency_key,
    )
