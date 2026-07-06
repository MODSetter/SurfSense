"""Shared credit-wallet primitives for the flat-rate per-unit billers.

Both :class:`app.services.web_crawl_credit_service.WebCrawlCreditService` and
:class:`app.services.platform_scrape_credit_service.PlatformScrapeCreditService`
follow the same gate -> pre-check -> post-charge model against the unified
``User.credit_micros_*`` wallet. The wallet math lives here once instead of
being copied per service:

- :func:`spendable_micros` — ``balance - reserved`` (ungated by any flag)
- :func:`check_balance` — raise :class:`InsufficientCreditsError` if short
- :func:`apply_debit` — debit + commit + best-effort auto-reload

``InsufficientCreditsError`` is re-exported from ``etl_credit_service`` so every
per-unit biller (ETL, crawl, platform scrape) shares one "out of credit" type —
the capability doors already catch exactly that one.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.etl_credit_service import InsufficientCreditsError

__all__ = ["InsufficientCreditsError", "apply_debit", "check_balance", "spendable_micros"]


async def spendable_micros(session: AsyncSession, user_id: str | UUID) -> int:
    """Raw ``balance - reserved`` read, **ungated** by any billing flag."""
    from app.db import User

    result = await session.execute(
        select(User.credit_micros_balance, User.credit_micros_reserved).where(
            User.id == user_id
        )
    )
    row = result.first()
    if not row:
        raise ValueError(f"User with ID {user_id} not found")

    balance, reserved = row
    return balance - reserved


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
    new balance in micros, or ``None`` when nothing was charged.
    """
    if cost_micros <= 0:
        return None

    from app.db import User

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.unique().scalar_one_or_none()
    if not user:
        raise ValueError(f"User with ID {user_id} not found")

    user.credit_micros_balance -= cost_micros
    await session.commit()
    await session.refresh(user)

    # Best-effort: fire an auto-reload check if the balance dropped low.
    try:
        from app.services.auto_reload_service import maybe_trigger_auto_reload

        await maybe_trigger_auto_reload(user_id)
    except Exception:
        pass

    return user.credit_micros_balance
