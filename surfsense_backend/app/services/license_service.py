"""Issue, look up and deliver Keygen-backed offline licenses.

There is no license table. Stripe and Keygen are the system of record, and
every lookup is a filter over Keygen license ``metadata``. Nothing in this
module takes a database session or touches Postgres.

Spec: ``plans/community-local/portal/01-license-routes.md``.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from app.config import config
from app.mailer import (
    build_license_email,
    get_mailer,
    is_mail_enabled,
)
from app.mailer.protocol import LicenseEmailKind
from app.services import keygen
from app.services.keygen import LicensePlan
from app.services.license_email import fold_email, normalize_email
from app.services.license_locks import license_lock

logger = logging.getLogger(__name__)

LicenseSource = Literal["stripe", "trial", "enterprise"]
_PAID_STATUSES = {"paid", "no_payment_required"}

# Keygen camelCases metadata keys in filter queries, so these are the spellings
# both writes and lookups must use.
META_EMAIL = "email"
META_PLAN = "plan"
META_CUSTOMER = "stripeCustomerId"
META_SESSION = "checkoutSessionId"
# Trials carry a second index. ``email`` is the address as typed, because that
# is where mail goes and what resend looks up; ``trialKey`` is the folded form
# the one-trial-per-person check filters on. Storing only the folded form would
# misdirect delivery, and storing only the typed form would let a tagged
# address claim a trial the fold could never find again.
META_TRIAL_KEY = "trialKey"


class LicenseIssueError(RuntimeError):
    """A checkout session that cannot be turned into a license."""


class TrialAlreadyClaimedError(RuntimeError):
    """This address has already taken its one trial."""


@dataclass(frozen=True, slots=True)
class IssuedLicense:
    """One license as it exists for the duration of a request. Never persisted."""

    keygen_license_id: str
    certificate: str
    plan: LicensePlan
    email: str
    max_users: int | None = None


# --------------------------------------------------------------------------
# Stripe session parsing
# --------------------------------------------------------------------------


def _metadata_of(obj: Any) -> dict[str, str]:
    metadata = getattr(obj, "metadata", None)
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        return {str(key): str(value) for key, value in to_dict(recursive=False).items()}
    return {}


def _customer_email(checkout_session: Any) -> str:
    details = getattr(checkout_session, "customer_details", None)
    email = (
        details.get("email")
        if isinstance(details, dict)
        else getattr(details, "email", None)
    )
    if not email or not str(email).strip():
        raise LicenseIssueError("License checkout session has no customer email")
    return normalize_email(str(email))


def _customer_id(checkout_session: Any) -> str | None:
    customer = getattr(checkout_session, "customer", None)
    if isinstance(customer, str):
        return customer or None
    return str(getattr(customer, "id", "")) or None


def _line_items(checkout_session: Any, *, stripe_client: Any) -> list[Any]:
    """Line items for the session, fetching them if Stripe did not expand them.

    Webhook payloads never carry line items, so a Payment Link purchase needs
    one extra call to learn which price was bought.
    """
    existing = getattr(checkout_session, "line_items", None)
    data = getattr(existing, "data", None) if existing is not None else None
    if data:
        return list(data)
    if stripe_client is None:
        return []

    session_id = str(getattr(checkout_session, "id", "") or "")
    if not session_id:
        return []
    expanded = stripe_client.v1.checkout.sessions.retrieve(
        session_id, params={"expand": ["line_items"]}
    )
    items = getattr(expanded, "line_items", None)
    # Cache onto the session: the webhook classifies a session and then
    # fulfils it, and without this a Payment Link purchase pays for the same
    # lookup twice.
    with contextlib.suppress(AttributeError, TypeError):
        checkout_session.line_items = items
    return list(getattr(items, "data", None) or [])


def _price_id(line_item: Any) -> str:
    price = getattr(line_item, "price", None)
    if isinstance(price, str):
        return price
    return str(getattr(price, "id", "") or "")


def resolve_license_plan(
    checkout_session: Any,
    *,
    stripe_client: Any = None,
) -> tuple[LicensePlan, int | None] | None:
    """Work out which license a paid session bought, or ``None`` if it is not one.

    Two sources, in order:

    1. Session metadata (``plan`` / ``quantity``), set by an API-created
       checkout session.
    2. The line item's price ID, matched against the configured license
       prices. Payment Links carry no session metadata, and supporting both
       means the Payment-Link-vs-API decision never blocks this code.
    """
    metadata = _metadata_of(checkout_session)
    if metadata.get("purchase_type") == "license":
        raw_plan = metadata.get("plan")
        if raw_plan not in {"individual", "team"}:
            raise LicenseIssueError(f"Unsupported license plan: {raw_plan!r}")
        plan = cast(LicensePlan, raw_plan)
        if plan != "team":
            return plan, None
        try:
            quantity = int(metadata["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LicenseIssueError("Team license quantity must be an integer") from exc
        if quantity < 1:
            raise LicenseIssueError("Team license quantity must be at least 1")
        return plan, quantity

    individual_price = config.STRIPE_PRICE_LICENSE_INDIVIDUAL
    team_price = config.STRIPE_PRICE_LICENSE_TEAM
    if not (individual_price or team_price):
        return None

    for line_item in _line_items(checkout_session, stripe_client=stripe_client):
        price_id = _price_id(line_item)
        if individual_price and price_id == individual_price:
            return "individual", None
        if team_price and price_id == team_price:
            quantity = int(getattr(line_item, "quantity", 0) or 0)
            if quantity < 1:
                raise LicenseIssueError("Team license quantity must be at least 1")
            return "team", quantity
    return None


# --------------------------------------------------------------------------
# Issuing
# --------------------------------------------------------------------------


def _trial_expiry(now: datetime | None = None) -> datetime:
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
    stripe_session_id: str | None = None,
    stripe_customer_id: str | None = None,
    extra_metadata: dict[str, str] | None = None,
) -> IssuedLicense:
    """Create one Keygen license and check out its file."""
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
        expiry=_trial_expiry() if plan == "trial" else None,
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


async def _existing_for_session(session_id: str) -> IssuedLicense | None:
    """The license already issued for this checkout session, if any.

    This Keygen list is the idempotency check: with no table, there is no
    unique constraint to lean on.
    """
    matches = await keygen.list_licenses(metadata={META_SESSION: session_id}, limit=1)
    if not matches:
        return None
    return await _issued_from_keygen(matches[0])


async def _issued_from_keygen(license_record: dict[str, Any]) -> IssuedLicense:
    attributes = license_record.get("attributes") or {}
    metadata = attributes.get("metadata") or {}
    license_id = str(license_record.get("id") or "")
    certificate = await keygen.checkout_license(license_id)
    return IssuedLicense(
        keygen_license_id=license_id,
        certificate=certificate,
        plan=cast(LicensePlan, metadata.get(META_PLAN) or "individual"),
        email=str(metadata.get(META_EMAIL) or ""),
        max_users=attributes.get("maxUsers"),
    )


async def fulfill_license_session(
    checkout_session: Any,
    *,
    stripe_client: Any = None,
) -> IssuedLicense:
    """Idempotently issue the license a paid Stripe session bought."""
    if getattr(checkout_session, "payment_status", None) not in _PAID_STATUSES:
        raise LicenseIssueError("License checkout session is not paid")

    session_id = str(getattr(checkout_session, "id", "") or "").strip()
    if not session_id:
        raise LicenseIssueError("License checkout session id is required")

    resolved = resolve_license_plan(checkout_session, stripe_client=stripe_client)
    if resolved is None:
        raise LicenseIssueError("Checkout session is not a license purchase")
    plan, max_users = resolved

    # The lock narrows the webhook-vs-success-page race; the Keygen list inside
    # it is the durable check.
    customer_id = _customer_id(checkout_session)
    async with license_lock(f"session:{session_id}"):
        existing = await _existing_for_session(session_id)
        if existing is not None:
            return existing

        issued = await issue_license(
            plan=plan,
            email=_customer_email(checkout_session),
            max_users=max_users,
            source="stripe",
            stripe_session_id=session_id,
            stripe_customer_id=customer_id,
        )

    if customer_id and stripe_client is not None:
        _record_license_on_customer(stripe_client, customer_id, issued)
    return issued


def _record_license_on_customer(
    stripe_client: Any, customer_id: str, issued: IssuedLicense
) -> None:
    """Write the Keygen license id onto the Stripe customer, for refunds.

    Best effort: the license is already issued, and raising here would fail the
    webhook and earn a Stripe retry that could duplicate it.
    """
    try:
        stripe_client.v1.customers.update(
            customer_id,
            params={"metadata": {"keygen_license_id": issued.keygen_license_id}},
        )
    except Exception:
        logger.warning(
            "Could not write keygen_license_id onto Stripe customer %s",
            customer_id,
            exc_info=True,
        )


async def issue_trial_license(email: str) -> IssuedLicense:
    """Issue one trial per email, or raise if this address already has one."""
    normalized = normalize_email(email)
    folded = fold_email(email)

    async with license_lock(f"trial:{folded}"):
        if await trial_exists(folded):
            raise TrialAlreadyClaimedError(folded)
        return await issue_license(
            plan="trial",
            email=normalized,
            source="trial",
            extra_metadata={META_TRIAL_KEY: folded},
        )


async def trial_exists(folded_email: str) -> bool:
    """Whether the trial policy already holds a license for this person.

    Filters on the folded key, not the delivery address, so ``a+one@`` and
    ``a+two@`` are one claimant.
    """
    matches = await keygen.list_licenses(
        metadata={META_TRIAL_KEY: folded_email},
        policy=config.KEYGEN_POLICY_TRIAL or None,
        limit=1,
    )
    return bool(matches)


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


async def certificates_for_email(email: str) -> list[str]:
    """Every license file registered to an address. The whole of "resend"."""
    matches = await keygen.list_licenses(metadata={META_EMAIL: normalize_email(email)})
    certificates: list[str] = []
    for record in matches:
        license_id = str(record.get("id") or "")
        if not license_id:
            continue
        certificates.append(await keygen.checkout_license(license_id))
    return certificates


async def certificate_for_checkout_session(
    session_id: str,
    *,
    stripe_client: Any = None,
) -> str | None:
    """The file for a checkout session, fulfilling it first if the webhook lags."""
    existing = await _existing_for_session(session_id)
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


async def suspend_licenses_for_customer(
    customer_id: str,
    *,
    keygen_license_id: str | None = None,
) -> int:
    """Suspend everything a refunded customer holds. Returns how many."""
    if keygen_license_id:
        await keygen.suspend_license(keygen_license_id)
        return 1

    matches = await keygen.list_licenses(metadata={META_CUSTOMER: customer_id})
    for record in matches:
        license_id = str(record.get("id") or "")
        if license_id:
            await keygen.suspend_license(license_id)
    return len(matches)


# --------------------------------------------------------------------------
# Support corrections
# --------------------------------------------------------------------------


class LicenseNotFoundError(RuntimeError):
    """No license matches the identifier support supplied."""


@dataclass(frozen=True, slots=True)
class LicenseRecord:
    """A license as Keygen holds it, for an operator to eyeball before editing."""

    keygen_license_id: str
    metadata: dict[str, str]
    max_users: int | None = None
    expiry: str | None = None


async def find_license_by_checkout_session(session_id: str) -> LicenseRecord:
    """Resolve the license a Stripe checkout produced.

    Support matches on the *payment*, not on how similar two addresses look:
    the buyer proves the charge in Stripe, Stripe gives the session id, and the
    session id names exactly one license. No judgement call about whether
    "gmial" meant "gmail".
    """
    matches = await keygen.list_licenses(metadata={META_SESSION: session_id}, limit=2)
    if not matches:
        raise LicenseNotFoundError(
            f"No license carries checkoutSessionId {session_id!r}"
        )
    if len(matches) > 1:
        # Two licenses for one payment means the idempotency race lost. Refuse
        # rather than guess which one the customer should keep.
        raise LicenseNotFoundError(
            f"{len(matches)} licenses carry checkoutSessionId {session_id!r}; "
            "resolve the duplicate in Keygen before correcting it"
        )
    record = matches[0]
    attributes = record.get("attributes") or {}
    return LicenseRecord(
        keygen_license_id=str(record.get("id") or ""),
        metadata=dict(attributes.get("metadata") or {}),
        max_users=attributes.get("maxUsers"),
        expiry=attributes.get("expiry"),
    )


async def correct_license_email(
    record: LicenseRecord,
    new_email: str,
) -> IssuedLicense:
    """Point a license at the address its buyer actually owns.

    Rewrites the stored address so the customer can use ``/license/resend``
    themselves from now on. Sending them the file without this leaves the typo
    in place and makes every future re-download a support ticket.
    """
    corrected = normalize_email(new_email)
    if not corrected:
        raise ValueError("A replacement email is required")

    metadata = dict(record.metadata)
    metadata[META_EMAIL] = corrected
    if metadata.get(META_PLAN) == "trial":
        # The dedupe index folds +tags; leaving the old key would let the
        # corrected address claim a second trial.
        metadata[META_TRIAL_KEY] = fold_email(corrected)

    await keygen.update_license_metadata(record.keygen_license_id, metadata)
    certificate = await keygen.checkout_license(record.keygen_license_id)
    logger.info(
        "Corrected license %s email %r -> %r",
        record.keygen_license_id,
        record.metadata.get(META_EMAIL),
        corrected,
    )
    return IssuedLicense(
        keygen_license_id=record.keygen_license_id,
        certificate=certificate,
        plan=cast(LicensePlan, metadata.get(META_PLAN) or "individual"),
        email=corrected,
        max_users=record.max_users,
    )


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


async def deliver_licenses(
    kind: LicenseEmailKind,
    *,
    to: str,
    certificates: list[str] | tuple[str, ...],
    idempotency_key: str | None = None,
) -> None:
    """Mail license files, if a provider is configured.

    Silently doing nothing under the ``null`` transport is the failure mode
    this guards against elsewhere: routes check ``is_mail_enabled`` first and
    answer 503. This check is the backstop for non-route callers.
    """
    if not certificates:
        return
    if not is_mail_enabled():
        logger.warning(
            "Not sending %s license mail to %s: no mail transport configured", kind, to
        )
        return

    message = build_license_email(
        kind,
        to=normalize_email(to),
        certificates=tuple(certificates),
        idempotency_key=idempotency_key,
    )
    await get_mailer().send(message)
