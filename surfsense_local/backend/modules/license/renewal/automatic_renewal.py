"""The app's own renewal check: a Business license near or just past its end.

A Business license ends 30 days after the period paid for, so a renewal the
server already holds arrives before the user misses it.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from api.dependencies import transact
from modules.license import service
from modules.license.renewal.license_refresh import refresh_license
from modules.license.renewal.refresh_failed import RefreshFailedError
from modules.license.verify import LicenseRejectedError

RENEW_WITHIN = timedelta(days=30)
# Past this, nothing on the server extends the license but support by hand, and
# each check would still tell the server the app is running. Covers a late invoice.
GIVE_UP_AFTER = timedelta(days=30)

logger = logging.getLogger(__name__)


async def renew_if_due(session_factory: sessionmaker[Session]) -> None:
    """Asks the license server only when due; a failure waits for the next check."""
    with session_factory() as session:
        if not await transact(session, _due):
            return
        try:
            renewed = await refresh_license(session)
        except RefreshFailedError as failed:
            # A host not allowed in Settings > Network is refresh_egress_blocked:
            # nothing was sent, and no dialog can ask from here (ADR 0060).
            logger.info("license renewal not fetched: %s", failed.code)
        except LicenseRejectedError as rejected:
            logger.warning("license renewal refused on import: %s", rejected.code)
        else:
            logger.info("license renewal checked; the license ends %s", renewed.expiry)


def _due(session: Session) -> bool:
    current = service.status(session)
    # A trial, the Business one included, is extended only by hand: Settings' button.
    if current.plan != "business" or current.expiry is None:
        return False
    left = current.expiry - service.now()
    return -GIVE_UP_AFTER <= left <= RENEW_WITHIN
