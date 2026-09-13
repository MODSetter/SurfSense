"""Subjects and bodies for the three license emails.

Copy lives on our side of the port, never in a transport and never hosted at
a vendor. That is what keeps switching provider from becoming a copy
migration.
"""

from __future__ import annotations

from .protocol import Attachment, LicenseEmail, LicenseEmailKind

LICENSE_FILENAME = "surfsense.lic"

_INSTALL_STEPS = (
    "1. Save the attached surfsense.lic somewhere you can find it.\n"
    "2. Open SurfSense and go to Settings -> License.\n"
    "3. Drop the file in, or paste its contents.\n"
)

_SUBJECTS: dict[LicenseEmailKind, str] = {
    "purchase": "Your SurfSense license",
    "resend": "Your SurfSense license (resent)",
    "trial": "Your SurfSense 14-day trial license",
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
        "Your 14-day SurfSense trial license is attached.\n\n"
        "When it expires the app keeps working and your data stays put -- only "
        "plugins and priority support stop."
    ),
}


def build_license_email(
    kind: LicenseEmailKind,
    *,
    to: str,
    certificates: tuple[str, ...],
    idempotency_key: str | None = None,
) -> LicenseEmail:
    """Render one message carrying every certificate issued to ``to``.

    A resend can legitimately carry more than one file (an individual license
    and a team license bought with the same address), so attachments are
    numbered once there is more than one.
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

    plural = "" if len(certificates) == 1 else f" ({len(certificates)} files)"
    body = f"{_INTROS[kind]}\n\n{_INSTALL_STEPS}\n"
    if plural:
        body = (
            f"{_INTROS[kind]}\n\n"
            f"{len(certificates)} licenses are registered to this address; all "
            "are attached. Import the one for the plan you want to use.\n\n"
            f"{_INSTALL_STEPS}\n"
        )

    return LicenseEmail(
        to=to,
        kind=kind,
        subject=_SUBJECTS[kind] + plural,
        text_body=body,
        attachments=attachments,
        idempotency_key=idempotency_key,
    )
