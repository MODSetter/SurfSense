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
from typing import Literal

from license.models import IssuedLicense
from license.release import InstallerLink, installer_links
from license.settings import config
from mailer.protocol import Attachment, OutboundEmail
from mailer.settings import config as mail_config

LicenseEmailKind = Literal["purchase", "resend", "trial", "renewal"]

LICENSE_FILENAME = "surfsense.lic"

# The same steps below, with screenshots of each one. Plain text cannot show
# where the gear is, so the mail carries both: the four lines for a reader who
# wants no detour, and the page for one who is stuck on a step.
ACTIVATION_GUIDE_URL = "https://www.surfsense.com/license/activate"


@dataclass(frozen=True, slots=True)
class BusinessCopy:
    """Business mail, for a Business license or trial: the firm and its people when known.

    Its own words, because the Individual promises do not hold for it: the app
    fetches a renewed file, and the license counts people, not machines.
    """

    firm: str | None = None
    people: int | None = None

    @classmethod
    def of(cls, issued: IssuedLicense) -> BusinessCopy | None:
        """For a license that unlocks the jobs; ``None`` keeps the copy as it was."""
        if issued.plan != "business" and not issued.jobs:
            return None
        people = issued.max_users if issued.plan == "business" else None
        return cls(firm=issued.firm, people=people)


def _install_steps(installers: tuple[InstallerLink, ...]) -> str:
    """Steps from nothing to a working license.

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
        "The app never contacts a license server: the file is verified offline "
        "and works on every machine you install SurfSense on."
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
}


def _manage_line() -> str:
    """How a firm changes its people or cancels, with no SurfSense account."""
    portal = config.STRIPE_CUSTOMER_PORTAL_URL
    if portal:
        return (
            f"To add or remove people, or to cancel, use the billing portal: {portal}"
        )
    return "To add or remove people, or to cancel, reply to this email."


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
    )
    # A trial has nothing to cancel; every paid kind names the portal.
    return intro if kind == "trial" else f"{intro}\n\n{_manage_line()}"


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
    if business is None:
        subject = _SUBJECTS[kind].format(days=days)
        intro = _INTROS[kind].format(days=days)
    else:
        subject = _BUSINESS_SUBJECTS[kind].format(days=days)
        intro = _business_intro(kind, business, days)
    steps = _install_steps(installer_links())

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
