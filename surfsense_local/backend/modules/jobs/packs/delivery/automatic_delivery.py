"""The app's own job-pack check: due for an active licence with jobs, whatever its plan, so the
Business trial gets its pack too. It never asks to reach the licence server: a host off in
Settings > Network is logged, and nothing is sent (ADR 0060). A code a run held back is
checked again the same way once the run ends."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, sessionmaker

from api.dependencies import transact_fresh
from modules.jobs.packs.delivery.deliver import DeliveryRefusedError, deliver_packs
from modules.jobs.packs.delivery.held_back import HELD_BACK
from modules.jobs.runs.in_flight import pack_in_use

logger = logging.getLogger(__name__)

# Outcomes a person should look into: the rest are a server's answer or the next check's.
_WORTH_A_WARNING = frozenset({"refused", "not_written"})


async def deliver_if_due(
    sessions: sessionmaker[Session], entitlements: list[str] | None = None
) -> None:
    """Checks `entitlements`, or every job the licence includes, and logs each outcome."""
    try:
        delivery = await deliver_packs(sessions, entitlements)
    except DeliveryRefusedError as refused:
        logger.info("job packs not checked: %s", refused.code)
        return
    if delivery.refusal is not None:
        logger.info(
            "job packs not checked: egress_blocked for %s", delivery.refusal.host
        )
        return
    for outcome in delivery.outcomes:
        logger.log(
            logging.WARNING if outcome.outcome in _WORTH_A_WARNING else logging.INFO,
            "job pack for %s: %s%s",
            outcome.entitlement,
            outcome.outcome,
            f" ({outcome.detail})" if outcome.detail else "",
        )


async def deliver_held_back(sessions: sessionmaker[Session]) -> None:
    """Checks once more each code a run held back whose pack no run is pending or processing
    for any more, reading only the runs: the installed packs are not read again."""
    held = HELD_BACK.held()
    if not held:
        return
    ended = await transact_fresh(sessions, _runs_ended, held)
    if not ended:
        return
    # Out of the record before the check: one held back again is recorded again, and any
    # other end, a refusal or a licence gone among them, is that code's last follow-up.
    HELD_BACK.release(ended)
    logger.info("job packs checked again once their runs ended: %s", ", ".join(ended))
    await deliver_if_due(sessions, ended)


def _runs_ended(session: Session, held: dict[str, str]) -> list[str]:
    return [code for code, pack_id in held.items() if not pack_in_use(session, pack_id)]
