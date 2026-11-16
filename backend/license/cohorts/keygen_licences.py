"""Every Keygen licence, split into trials and purchases."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import date, datetime
from typing import Any

from license import keygen
from license.email.address import fold_email
from license.models import META_EMAIL, META_PLAN, META_SESSION, META_TRIAL_KEY
from license.records import is_suspended

from .models import Purchase, Trial

LicenceSource = Callable[[], AsyncIterator[dict[str, Any]]]


async def read_licences(
    licences: LicenceSource = keygen.iter_licenses,
) -> tuple[list[Trial], list[Purchase]]:
    trials: list[Trial] = []
    purchases: list[Purchase] = []
    async for record in licences():
        attributes = record.get("attributes") or {}
        metadata = attributes.get("metadata") or {}
        created = _day(attributes.get("created"))
        if created is None:
            continue
        email = str(metadata.get(META_EMAIL) or "")
        if metadata.get(META_PLAN) == "trial":
            # trialKey follows a support correction; the typed address may not.
            folded = str(metadata.get(META_TRIAL_KEY) or "") or fold_email(email)
            trials.append(Trial(str(record.get("id") or ""), created, folded))
        else:
            purchases.append(
                Purchase(
                    paid_on=created,
                    folded_emails={fold_email(email)} if email else set(),
                    # A full refund suspends the licence (``purchase.py``).
                    refunded=is_suspended(record),
                    checkout_session_id=metadata.get(META_SESSION) or None,
                )
            )
    return trials, purchases


def _day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None
