"""Shared credit-wallet primitives.

Both :class:`app.services.web_crawl_credit_service.WebCrawlCreditService` and
:class:`app.services.platform_scrape_credit_service.PlatformScrapeCreditService`
follow the same gate -> pre-check -> post-charge model against the unified
``User.credit_micros_*`` wallet. The wallet math lives here once instead of
being copied per service:

- :func:`funds_micros` — ``allowance + balance`` for an already-loaded user
- :func:`drain` — charge a cost against that user, allowance first
- :func:`spendable_micros` — ``allowance + balance - reserved`` (ungated)
- :func:`check_balance` — raise :class:`InsufficientCreditsError` if short
- :func:`apply_debit` — debit + commit + best-effort auto-reload

The wallet holds two buckets. ``credit_micros_allowance`` is the plan grant: it
resets each period and does not roll over. ``credit_micros_balance`` is
permanent money — purchases, incentive rewards, auto-reload top-ups. Every
debit path routes through :func:`drain` so the ordering between them is decided
in exactly one place; ``token_quota_service`` (premium model calls) and
``EtlCreditService`` (page processing) both call it rather than touching the
columns directly.

``InsufficientCreditsError`` is re-exported from ``etl_credit_service`` so every
per-unit biller (ETL, crawl, platform scrape) shares one "out of credit" type —
the capability doors already catch exactly that one.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.services.etl_credit_service import InsufficientCreditsError

if TYPE_CHECKING:
    from app.db import User

__all__ = [
    "InsufficientCreditsError",
    "apply_debit",
    "check_balance",
    "drain",
    "funds_micros",
    "has_ever_paid",
    "roll_allowance_if_due",
    "spendable_micros",
    "start_first_allowance_period",
]


def funds_micros(user: "User") -> int:
    """Total spendable-before-reservations credit for a loaded user row.

    Allowance and balance are one pot as far as affordability goes; they only
    differ in which one :func:`drain` empties first and which one expires.
    """
    return max(0, user.credit_micros_allowance) + user.credit_micros_balance


def drain(user: "User", cost_micros: int) -> None:
    """Charge ``cost_micros`` against a loaded user row, allowance first.

    The plan allowance is spent ahead of ``credit_micros_balance`` so a user's
    purchased credit is only touched once the period's included usage is gone —
    which turns any balance they bought into overage protection rather than the
    first thing to disappear.

    Any shortfall lands on the balance, which is allowed to go negative: an
    actual provider cost can exceed the pre-charge estimate on a request that
    has already run, and the UI clamps the display at $0. Does not commit —
    the caller owns the transaction.
    """
    if cost_micros <= 0:
        return
    from_allowance = min(max(0, user.credit_micros_allowance), cost_micros)
    user.credit_micros_allowance -= from_allowance
    user.credit_micros_balance -= cost_micros - from_allowance


async def has_ever_paid(session: AsyncSession, user_id: str | UUID) -> bool:
    """True if the user has ever completed a purchase that moved real money.

    ``amount_total`` is what Stripe actually charged, so this excludes the
    signup grant and any incentive reward — rows that exist to be auditable,
    not because anyone paid.
    """
    from app.db import CreditPurchase, CreditPurchaseStatus

    result = await session.execute(
        select(CreditPurchase.id)
        .where(
            CreditPurchase.user_id == user_id,
            CreditPurchase.status == CreditPurchaseStatus.COMPLETED,
            CreditPurchase.amount_total > 0,
        )
        .limit(1)
    )
    return result.first() is not None


async def roll_allowance_if_due(
    session: AsyncSession, user: "User", *, now: datetime | None = None
) -> bool:
    """Start a new allowance period for a free user whose period has ended.

    Lazy on purpose: the check runs where the user row is already loaded and
    locked, so no cron has to sweep every account to keep grants current.

    A null ``allowance_period_end`` means the account has never been on a
    period, so it starts one here. That covers accounts predating the plan
    columns as well as any signup whose best-effort grant did not land, which
    is what makes this the safety net rather than a second code path that can
    silently disagree with the first.

    **Only the free plan self-grants here.** A paid allowance is granted by the
    ``invoice.paid`` webhook, which carries the period Stripe actually billed.
    Re-granting a paid plan on a timer would hand out a month of usage to
    someone whose card just failed.

    Returns True when the user row was modified. Does not commit.
    """
    now = now or datetime.now(UTC)
    period_end = user.allowance_period_end
    if period_end is not None and period_end > now:
        return False
    if user.plan != "free":
        return False

    user.credit_micros_allowance = config.plan_allowance_micros(user.plan)
    user.allowance_period_end = now + timedelta(days=30)

    # A run can settle past everything the wallet held, leaving the balance
    # negative (bounded near -$1.95, the priciest single call observed). For
    # someone who never paid us, carrying that forward would cost them the
    # next month or two over one tail run they did not cause, so it is written
    # off. A buyer's debt stands and nets against their next top-up.
    if user.credit_micros_balance < 0 and not await has_ever_paid(session, user.id):
        user.credit_micros_balance = 0
    return True


async def start_first_allowance_period(
    session: AsyncSession, user_id: str | UUID, *, now: datetime | None = None
) -> int:
    """Give a new free account its first allowance period; returns micros granted.

    Brings forward what :func:`roll_allowance_if_due` would do anyway on the
    account's first premium turn, so the credit is visible from signup instead
    of appearing only after the first question. Deliberately *not* gated on the
    signup-credit identity claim: the lazy roll is ungated, so gating here would
    only delay the same grant to the first turn while breaking the free plan for
    anyone's legitimate second account.

    Issues an UPDATE rather than mutating a row, because the caller's ``user``
    belongs to the auth session rather than this one. The null check makes it
    idempotent and stops it overwriting a period already under way. Does not
    commit.
    """
    from app.db import User

    granted = config.plan_allowance_micros("free")
    if granted <= 0:
        return 0

    now = now or datetime.now(UTC)
    await session.execute(
        update(User)
        .where(User.id == user_id, User.allowance_period_end.is_(None))
        .values(
            credit_micros_allowance=granted,
            allowance_period_end=now + timedelta(days=30),
        )
    )
    return granted


async def spendable_micros(session: AsyncSession, user_id: str | UUID) -> int:
    """Raw ``allowance + balance - reserved`` read, **ungated** by any flag."""
    from app.db import User

    result = await session.execute(
        select(
            User.credit_micros_allowance,
            User.credit_micros_balance,
            User.credit_micros_reserved,
        ).where(User.id == user_id)
    )
    row = result.first()
    if not row:
        raise ValueError(f"User with ID {user_id} not found")

    allowance, balance, reserved = row
    return max(0, allowance) + balance - reserved


async def check_balance(
    session: AsyncSession, user_id: str | UUID, required_micros: int
) -> None:
    """Raise :class:`InsufficientCreditsError` if the wallet can't cover
    ``required_micros``. Generic and **ungated** — the caller decides when at
    least one relevant biller is enabled. No-op for a non-positive requirement.
    """
    if required_micros <= 0:
        return
    available = await spendable_micros(session, user_id)
    if required_micros > available:
        raise InsufficientCreditsError(
            message=(
                "This run would exceed your available credit. "
                f"Available: ${available / 1_000_000:.2f}, "
                f"estimated need: ${required_micros / 1_000_000:.2f}. "
                "Add more credits to continue."
            ),
            balance_micros=available,
            required_micros=required_micros,
        )


async def apply_debit(
    session: AsyncSession, user_id: str | UUID, cost_micros: int
) -> int | None:
    """Debit ``cost_micros`` from the wallet and commit.

    Flushes any audit row the caller staged before this, then fires a
    best-effort auto-reload check. No-op for a non-positive cost; returns the
    new permanent balance in micros, or ``None`` when nothing was charged.
    Note the return is the balance alone, not the allowance — callers use it
    for the auto-reload nudge, which only ever tops up the balance.
    """
    if cost_micros <= 0:
        return None

    from app.db import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.unique().scalar_one_or_none()
    if not user:
        raise ValueError(f"User with ID {user_id} not found")

    drain(user, cost_micros)
    await session.commit()
    await session.refresh(user)

    # Best-effort: fire an auto-reload check if the balance dropped low.
    try:
        from app.services.auto_reload_service import maybe_trigger_auto_reload

        await maybe_trigger_auto_reload(user_id)
    except Exception:
        pass

    return user.credit_micros_balance
