"""Unauthenticated license routes: download, resend, trial.

There is no login on the portal and no license table. Stripe and Keygen are
the system of record, the license is tied to the buyer email in Keygen
metadata, and re-download is a resend to that address. Nothing here takes a
session, reads the user table, or touches Postgres.

Spec: ``plans/community-local/portal/01-license-routes.md``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config import config
from app.license.email.address import is_disposable, normalize_email
from app.license.email.deliver import deliver_licenses
from app.license.issue import certificate_for_checkout_session, issue_trial_license
from app.license.models import TrialAlreadyClaimedError
from app.license.rate_limit import enforce_license_rate_limit
from app.license.records import certificates_for_email
from app.license.schemas import LicenseAckResponse, LicenseEmailRequest
from app.mailer import MailerRejectedError, MailerUnavailableError, is_mail_enabled
from app.payments.client import get_stripe_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/license", tags=["license"])

# Deliberately identical for "mailed three files" and "found none", so the
# endpoint cannot be used to probe which addresses are customers.
_RESEND_ACK = "If a license is registered to that address, it is on its way."


def _license_file(certificate: str) -> Response:
    return Response(
        content=certificate,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="surfsense.lic"'},
    )


def _require_mailer() -> None:
    """Refuse rather than report a send that will not happen.

    ``/license/resend`` always answers 200 so it cannot be used as an email
    oracle, and the ``null`` transport also "succeeds" -- together they would
    make a misconfigured deployment indistinguishable from a working one.
    Checked before any Keygen lookup, so the 503 is outcome-independent and
    leaks nothing.
    """
    if not is_mail_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License email delivery is not configured.",
        )


def _stripe_client_or_none():
    try:
        return get_stripe_client()
    except HTTPException:
        # Stripe unconfigured: the Keygen lookup can still serve an already
        # fulfilled session.
        return None


@router.get("/file")
async def download_license(session_id: str) -> Response:
    """Serve a purchase's license file on the success page.

    ``session_id`` is required. The old build fell back to the signed-in user's
    email, which is the login coupling this design removes; there is no
    fallback to replace it.
    """
    certificate = await certificate_for_checkout_session(
        session_id, stripe_client=_stripe_client_or_none()
    )
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found.",
        )
    return _license_file(certificate)


@router.post("/resend", response_model=LicenseAckResponse)
async def resend_license(
    payload: LicenseEmailRequest,
    request: Request,
) -> LicenseAckResponse:
    """Mail every license registered to an address. Always answers 200."""
    _require_mailer()
    email = normalize_email(payload.email)
    await enforce_license_rate_limit(request, route="resend", email=email)

    try:
        certificates = await certificates_for_email(email)
        if certificates:
            await deliver_licenses("resend", to=email, certificates=certificates)
    except MailerRejectedError:
        # Reporting this would confirm the address exists as a customer.
        logger.info("Resend mail refused for an address; answering 200 regardless")
    except MailerUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the email right now. Please try again shortly.",
        ) from None
    except Exception:
        # Keygen failures must not become an oracle either.
        logger.exception("Resend lookup failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not process that request right now.",
        ) from None

    return LicenseAckResponse(detail=_RESEND_ACK)


@router.post("/trial", response_model=LicenseAckResponse)
async def claim_trial_license(
    payload: LicenseEmailRequest,
    request: Request,
) -> LicenseAckResponse:
    """Issue one 14-day trial per email and mail it.

    The file is never returned in the response: requiring delivery to a real
    inbox is what makes one-trial-per-email mean anything.
    """
    if not config.LICENSE_TRIAL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License trial is not available.",
        )
    _require_mailer()

    email = normalize_email(payload.email)
    await enforce_license_rate_limit(request, route="trial", email=email)

    if is_disposable(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use a permanent email address to start a trial.",
        )

    try:
        issued = await issue_trial_license(email)
    except TrialAlreadyClaimedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A trial license has already been claimed for that address.",
        ) from None
    except Exception:
        # Keygen unreachable or misconfigured. Resend already degrades to 503
        # here; without this the same outage gives trial an unhandled 500.
        #
        # The issue call is two Keygen requests, and a failure between them
        # leaves the trial created but undelivered -- the address is spent and
        # the caller has nothing. Point at resend, which finds that trial and
        # mails it, rather than leaving them to guess.
        logger.exception("Trial issuance failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Could not issue a trial right now. Try again shortly, and if "
                "it keeps failing use 'resend my license'."
            ),
        ) from None

    try:
        await deliver_licenses(
            "trial",
            to=email,
            certificates=[issued.certificate],
            idempotency_key=issued.keygen_license_id,
        )
    except MailerRejectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That email address was refused by its mail server.",
        ) from None
    except MailerUnavailableError:
        # The license exists; the trial is claimed. Say so honestly rather
        # than implying the address is now burned for nothing.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Your trial was created but the email could not be sent. "
                "Use 'resend my license' in a few minutes."
            ),
        ) from None

    return LicenseAckResponse(detail="Your trial license is on its way.")
