"""Minting licenses: paid purchases and the one-per-person trial."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import config
from app.license import keygen
from app.license.checkout import customer_email, customer_id, resolve_license_plan
from app.license.email.address import fold_email, normalize_email
from app.license.keygen import LicensePlan
from app.license.models import (
    META_CUSTOMER,
    META_SESSION,
    META_TRIAL_KEY,
    PAID_STATUSES,
    IssuedLicense,
    LicenseIssueError,
    LicenseSource,
    TrialAlreadyClaimedError,
)
from app.license.records import existing_for_session, issued_for_id

logger = logging.getLogger(__name__)

# Changing this namespace changes every derived id, so an in-flight purchase
# could be fulfilled twice across the deploy that changes it. It is a constant
# for that reason, not configuration.
_LICENSE_NAMESPACE = uuid.UUID("75511ef3-567a-4f1d-8aaa-8d62f1883751")


def derive_license_id(scope: str, identity: str) -> str:
    """The Keygen id a given purchase or claimant must always produce.

    This is the whole concurrency story. Two callers can fulfil one payment at
    the same instant -- the webhook and the buyer's success page -- and with no
    license table there is no unique row to collide on. Deriving the record's
    id from the purchase moves the collision into Keygen, which refuses the
    second create atomically and account-wide. The loser then reads the
    winner's license instead of minting a second one.

    Only the id is derived. The license *key* stays Keygen-generated, because
    that is the bearer credential contract 2 sends to the scraper API and must
    be unguessable; an id is a handle that does nothing without an API token,
    so it costs no secret to make it predictable.
    """
    return str(uuid.uuid5(_LICENSE_NAMESPACE, f"{scope}:{identity}"))


def trial_expiry(now: datetime | None = None) -> datetime:
    """When a trial issued right now should expire.

    While the scraper plugin has not shipped, the clock starts at the plugin
    date rather than today, so the gap week does not eat the trial. With the
    floor unset this is plain "N days from now", which is correct once the
    plugin is out.
    """
    now = now or datetime.now(UTC)
    start = now
    floor = config.LICENSE_TRIAL_EXPIRY_FLOOR
    if floor:
        try:
            parsed = datetime.fromisoformat(floor)
        except ValueError:
            logger.warning(
                "LICENSE_TRIAL_EXPIRY_FLOOR=%r is not an ISO date; ignoring", floor
            )
        else:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            start = max(now, parsed)
    return start + timedelta(days=config.LICENSE_TRIAL_DAYS)


async def issue_license(
    *,
    plan: LicensePlan,
    email: str,
    max_users: int | None = None,
    source: LicenseSource,
    license_id: str | None = None,
    stripe_session_id: str | None = None,
    stripe_customer_id: str | None = None,
    extra_metadata: dict[str, str] | None = None,
) -> IssuedLicense:
    """Create one Keygen license and check out its file.

    Raises :class:`keygen.LicenseExistsError` when ``license_id`` is already
    taken, which is how callers learn they lost a race rather than by looking
    first.
    """
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise LicenseIssueError("License email is required")
    if plan != "team":
        max_users = None

    metadata: dict[str, str] = dict(extra_metadata or {})
    if stripe_session_id:
        metadata[META_SESSION] = stripe_session_id
    if stripe_customer_id:
        metadata[META_CUSTOMER] = stripe_customer_id

    keygen_license_id = await keygen.create_license(
        plan,
        normalized_email,
        max_users,
        license_id=license_id,
        expiry=trial_expiry() if plan == "trial" else None,
        extra_metadata=metadata or None,
    )
    certificate = await keygen.checkout_license(keygen_license_id)
    logger.info(
        "Issued %s license %s for %s (source=%s)",
        plan,
        keygen_license_id,
        normalized_email,
        source,
    )
    return IssuedLicense(
        keygen_license_id=keygen_license_id,
        certificate=certificate,
        plan=plan,
        email=normalized_email,
        max_users=max_users,
    )


async def fulfill_license_session(
    checkout_session: Any,
    *,
    stripe_client: Any = None,
) -> IssuedLicense:
    """Idempotently issue the license a paid Stripe session bought."""
    if getattr(checkout_session, "payment_status", None) not in PAID_STATUSES:
        raise LicenseIssueError("License checkout session is not paid")

    session_id = str(getattr(checkout_session, "id", "") or "").strip()
    if not session_id:
        raise LicenseIssueError("License checkout session id is required")

    resolved = resolve_license_plan(checkout_session, stripe_client=stripe_client)
    if resolved is None:
        raise LicenseIssueError("Checkout session is not a license purchase")
    plan, max_users = resolved

    # No look-before-create: the id is derived from the session, so a second
    # caller fulfilling the same payment collides inside Keygen rather than
    # reading "not found" a moment before the first one writes.
    stripe_customer = customer_id(checkout_session)
    license_id = derive_license_id("stripe", session_id)
    try:
        issued = await issue_license(
            plan=plan,
            email=customer_email(checkout_session),
            max_users=max_users,
            source="stripe",
            license_id=license_id,
            stripe_session_id=session_id,
            stripe_customer_id=stripe_customer,
        )
    except keygen.LicenseExistsError:
        existing = await issued_for_id(license_id)
        if existing is None:
            # Only reachable if the winner's license was deleted between its
            # create and this lookup. Retrying would collide again.
            raise LicenseIssueError(
                f"License for session {session_id} exists but is unreadable"
            ) from None
        logger.info(
            "Session %s was already fulfilled as license %s; reusing it",
            session_id,
            existing.keygen_license_id,
        )
        return existing

    if stripe_customer and stripe_client is not None:
        _record_license_on_customer(stripe_client, stripe_customer, issued)
    return issued


def _record_license_on_customer(
    stripe_client: Any, customer: str, issued: IssuedLicense
) -> None:
    """Write the Keygen license id onto the Stripe customer, for refunds.

    Best effort: the license is already issued, and raising here would fail the
    webhook and earn a Stripe retry that could duplicate it.
    """
    try:
        stripe_client.v1.customers.update(
            customer,
            params={"metadata": {"keygen_license_id": issued.keygen_license_id}},
        )
    except Exception:
        logger.warning(
            "Could not write keygen_license_id onto Stripe customer %s",
            customer,
            exc_info=True,
        )


async def issue_trial_license(email: str) -> IssuedLicense:
    """Issue one trial per email, or raise if this address already has one.

    The key folds the address, so ``a+one@`` and ``a+two@`` are one claimant,
    and Keygen refuses the second create outright. One-trial-per-person is
    therefore enforced by the store rather than by a lookup that two
    simultaneous claims could both pass.
    """
    normalized = normalize_email(email)
    folded = fold_email(email)

    # Two guards, because they answer different questions. The derived id is
    # the constraint: it is immutable, so it settles simultaneous claims by the
    # same address without anyone having to look first. ``trialKey`` is the
    # mutable index: support re-points it when it corrects a mistyped address,
    # and the id cannot follow, because a record's id is fixed once created.
    if await trial_exists(folded):
        raise TrialAlreadyClaimedError(folded)

    try:
        return await issue_license(
            plan="trial",
            email=normalized,
            source="trial",
            license_id=derive_license_id("trial", folded),
            extra_metadata={META_TRIAL_KEY: folded},
        )
    except keygen.LicenseExistsError:
        raise TrialAlreadyClaimedError(folded) from None


async def trial_exists(folded_email: str) -> bool:
    """Whether this person already holds a trial, by the mutable index.

    Filters on the folded key, not the delivery address, so ``a+one@`` and
    ``a+two@`` are one claimant. Racy on its own -- two simultaneous claims can
    both pass -- which is what the derived license key is there to catch.
    """
    matches = await keygen.list_licenses(
        metadata={META_TRIAL_KEY: folded_email},
        policy=config.KEYGEN_POLICY_TRIAL or None,
        limit=1,
    )
    return bool(matches)


async def certificate_for_checkout_session(
    session_id: str,
    *,
    stripe_client: Any = None,
) -> str | None:
    """The file for a checkout session, fulfilling it first if the webhook lags."""
    existing = await existing_for_session(session_id)
    if existing is not None:
        return existing.certificate

    if stripe_client is None:
        return None
    try:
        checkout_session = stripe_client.v1.checkout.sessions.retrieve(session_id)
        issued = await fulfill_license_session(
            checkout_session, stripe_client=stripe_client
        )
    except LicenseIssueError:
        return None
    except Exception:
        logger.warning(
            "Could not fulfil license for checkout session %s",
            session_id,
            exc_info=True,
        )
        return None
    return issued.certificate
