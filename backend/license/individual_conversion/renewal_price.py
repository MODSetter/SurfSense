"""Whether a subscription renews at the price its buyer paid, as the conversion notice says.

Individual's $60 was planned as a coupon on a $120 price, and the site sold it as
"$60 for the first year, then $120". A coupon that applies once leaves the
subscription's discounts once it is used, and a repeating one ends on a date
(Stripe's coupons guide), so a discounted year followed by no lasting discount
renews at more than was paid. Pure: it reads what was fetched.
"""

from __future__ import annotations

from typing import Any

from license.subscription.paid_period import items_of


def renews_above_price_paid(subscription: Any, newest_period_invoice: Any) -> bool:
    """The year last paid for was discounted, and no discount on it lasts."""
    if newest_period_invoice is None or not _discounted(newest_period_invoice):
        return False
    return not any(_lasts(discount) for discount in _discounts(subscription))


def _discounted(invoice: Any) -> bool:
    amounts = getattr(invoice, "total_discount_amounts", None) or []
    return sum(getattr(amount, "amount", 0) or 0 for amount in amounts) > 0


def _discounts(subscription: Any) -> list[Any]:
    """The subscription's discounts and its items', as retrieved with them expanded."""
    found = list(getattr(subscription, "discounts", None) or [])
    for item in items_of(subscription):
        found.extend(getattr(item, "discounts", None) or [])
    return found


def _lasts(discount: Any) -> bool:
    """A discount with no end: a forever coupon's.

    A once coupon's has no end either but leaves when its invoice finalizes, so
    the year paid for used it up; one added since reads as lasting. An id, not
    expanded, is not known to last.
    """
    if isinstance(discount, str):
        return False
    return getattr(discount, "end", None) is None
