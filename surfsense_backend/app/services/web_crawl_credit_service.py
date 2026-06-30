"""Service for charging the unified credit wallet per successful web crawl.

Deliberately mirrors :class:`app.services.etl_credit_service.EtlCreditService`:
a simple **gate -> pre-check -> post-charge** model (no reserve/finalize),
because a crawl has no LLM token accumulator to settle against. The billable
unit is one *successful* crawl (``CrawlOutcomeStatus.SUCCESS``).

The price is **fully config-driven** — there is no hardcoded rate anywhere.
``config.WEB_CRAWL_MICROS_PER_SUCCESS`` is the single source of truth (default
``1000`` micro-USD == $1 / 1000 crawls); retune it via env + restart, no code
change. When ``config.WEB_CRAWL_CREDIT_BILLING_ENABLED`` is False (the default
for self-hosted / OSS installs) every check/charge is a no-op, preserving the
prior effectively-free crawl behaviour.

``billing_enabled()`` and ``successes_to_micros()`` are exposed as static
helpers so the chat ``scrape_webpage`` tools can share the flag/price math:
they fold a single success into the current chat turn's existing bill (via the
turn accumulator) instead of debiting the wallet directly.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config

# Reuse the ETL service's error type so callers (and tests) have one exception
# to catch for "out of credit" across every per-unit wallet biller.
from app.services.etl_credit_service import InsufficientCreditsError

__all__ = ["InsufficientCreditsError", "WebCrawlCreditService"]


class WebCrawlCreditService:
    """Checks and charges the credit wallet for successful web crawls."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def billing_enabled() -> bool:
        return config.WEB_CRAWL_CREDIT_BILLING_ENABLED

    @staticmethod
    def successes_to_micros(successes: int) -> int:
        """Convert a successful-crawl count to USD micro-credits.

        Reads ``config.WEB_CRAWL_MICROS_PER_SUCCESS`` — the single, env-tunable
        source of truth for crawl price.
        """
        return int(successes) * config.WEB_CRAWL_MICROS_PER_SUCCESS

    async def get_available_micros(self, user_id: str | UUID) -> int | None:
        """Return spendable credit in micro-USD (``balance - reserved``).

        Returns ``None`` when crawl billing is disabled, which callers treat as
        "unlimited" (no blocking, no charge).
        """
        if not config.WEB_CRAWL_CREDIT_BILLING_ENABLED:
            return None

        from app.db import User

        result = await self.session.execute(
            select(User.credit_micros_balance, User.credit_micros_reserved).where(
                User.id == user_id
            )
        )
        row = result.first()
        if not row:
            raise ValueError(f"User with ID {user_id} not found")

        balance, reserved = row
        return balance - reserved

    async def check_credits(
        self, user_id: str | UUID, estimated_successes: int = 1
    ) -> None:
        """Raise :class:`InsufficientCreditsError` if the user can't afford
        ``estimated_successes`` crawls.

        No-op when crawl billing is disabled. ``estimated_successes`` is a safe
        upper bound (``len(urls)``) — actual successes are always <=, so a
        passing pre-flight guarantees the wallet can never go negative.
        """
        if not config.WEB_CRAWL_CREDIT_BILLING_ENABLED:
            return

        required = self.successes_to_micros(estimated_successes)
        available = await self.get_available_micros(user_id)
        if available is None:
            return

        if required > available:
            raise InsufficientCreditsError(
                message=(
                    "This crawl would exceed your available credit. "
                    f"Available: ${available / 1_000_000:.2f}. "
                    f"Up to {estimated_successes} URL(s) cost about "
                    f"${required / 1_000_000:.2f}. Add more credits to continue."
                ),
                balance_micros=available,
                required_micros=required,
            )

    async def charge_credits(
        self, user_id: str | UUID, successes: int
    ) -> int | None:
        """Debit the wallet for ``successes`` successful crawls.

        Commits the session (mirroring ``EtlCreditService.charge_credits``),
        which also flushes any audit row staged by the caller before this call.
        No-op when billing is disabled or ``successes <= 0``.

        Returns the new balance in micros, or ``None`` when nothing was charged.
        """
        if not config.WEB_CRAWL_CREDIT_BILLING_ENABLED:
            return None
        if successes <= 0:
            return None

        from app.db import User

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.unique().scalar_one_or_none()
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        cost = self.successes_to_micros(successes)
        user.credit_micros_balance -= cost
        await self.session.commit()
        await self.session.refresh(user)

        # Best-effort: fire an auto-reload check if the balance dropped low.
        try:
            from app.services.auto_reload_service import maybe_trigger_auto_reload

            await maybe_trigger_auto_reload(user_id)
        except Exception:
            pass

        return user.credit_micros_balance
