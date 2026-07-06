"""Charge the credit wallet per *item returned* by a platform-native scraper.

Deliberately mirrors :class:`app.services.web_crawl_credit_service.WebCrawlCreditService`:
a simple **gate -> pre-check -> post-charge** model (no reserve/finalize) — a
scrape has no LLM token accumulator to settle against. The billable unit is one
returned item (a Reddit post/comment, a SERP page, a Maps place/review, a
YouTube video/comment); the per-item rate is passed in by the caller from the
verb's config knob so this one service serves every platform meter.

The price is **fully config-driven** — there is no hardcoded rate here. When
``config.PLATFORM_SCRAPE_BILLING_ENABLED`` is False (the default for
self-hosted / OSS installs) every check/charge is a no-op, preserving the prior
effectively-free scraping behaviour.

Wallet math (spendable / check / debit) is shared with the crawl biller via
:mod:`app.services.wallet_credit`.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config

# One "out of credit" type across every per-unit biller; the capability doors
# already catch exactly this one.
from app.services.etl_credit_service import InsufficientCreditsError
from app.services import wallet_credit

__all__ = ["InsufficientCreditsError", "PlatformScrapeCreditService"]


class PlatformScrapeCreditService:
    """Checks and charges the credit wallet for platform scraper items."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def billing_enabled() -> bool:
        return config.PLATFORM_SCRAPE_BILLING_ENABLED

    @staticmethod
    def items_to_micros(items: int, rate_micros: int) -> int:
        """Convert an item count to USD micro-credits at ``rate_micros``/item."""
        return int(items) * int(rate_micros)

    async def check_credits(
        self, user_id: str | UUID, estimated_items: int, rate_micros: int
    ) -> None:
        """Raise :class:`InsufficientCreditsError` if the wallet can't afford
        ``estimated_items`` at ``rate_micros`` each.

        No-op when platform billing is disabled. ``estimated_items`` is a safe
        upper bound (the request's worst-case fan-out) so a passing pre-flight
        guarantees the wallet can never go negative.
        """
        if not config.PLATFORM_SCRAPE_BILLING_ENABLED:
            return
        required = self.items_to_micros(estimated_items, rate_micros)
        await wallet_credit.check_balance(self.session, user_id, required)

    async def charge(
        self, user_id: str | UUID, items: int, rate_micros: int
    ) -> int | None:
        """Debit the wallet for ``items`` returned at ``rate_micros`` each.

        No-op when platform billing is disabled or ``items <= 0``. Returns the
        new balance in micros, or ``None`` when nothing was charged.
        """
        if not config.PLATFORM_SCRAPE_BILLING_ENABLED:
            return None
        if items <= 0:
            return None
        return await wallet_credit.apply_debit(
            self.session, user_id, self.items_to_micros(items, rate_micros)
        )
