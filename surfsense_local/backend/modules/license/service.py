from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.license.models import LicenseState
from modules.license.verify import MAX_CLOCK_DRIFT, Verified, verify

State = Literal["none", "active", "license_expired", "clock_untrusted"]


class LicenseStatus(BaseModel):
    state: State
    plan: str | None = None
    email: str | None = None
    expiry: datetime | None = None
    max_users: int | None = None


def now() -> datetime:
    return datetime.now(UTC)


def import_certificate(session: Session, certificate: str) -> LicenseStatus:
    instant = now()
    verified = verify(certificate, instant)
    row = _row(session, instant)
    row.certificate = certificate
    row.imported_at = _naive(instant)
    return _status(row, verified, instant)


def remove_certificate(session: Session) -> None:
    row = _row(session, now())
    row.certificate = None
    row.imported_at = None


def status(session: Session) -> LicenseStatus:
    instant = now()
    row = _row(session, instant)
    if row.certificate is None:
        return LicenseStatus(state="none")
    return _status(row, verify(row.certificate, instant), instant)


def _status(row: LicenseState, verified: Verified, instant: datetime) -> LicenseStatus:
    # ponytail: the watermark lives in user-writable SQLite, so this is honesty
    # for the UI, not enforcement; the plugin scraper API is where money is kept.
    row.clock_watermark = max(
        row.clock_watermark, _naive(instant), _naive(verified.issued)
    )
    if _naive(instant) < row.clock_watermark - MAX_CLOCK_DRIFT:
        state: State = "clock_untrusted"
    elif verified.expiry > instant:
        state = "active"
    else:
        state = "license_expired"
    return LicenseStatus(
        state=state,
        plan=verified.plan,
        email=verified.email,
        expiry=verified.expiry,
        max_users=verified.max_users,
    )


def _row(session: Session, instant: datetime) -> LicenseState:
    row = session.get(LicenseState, 1)
    if row is None:
        row = LicenseState(clock_watermark=_naive(instant))
        session.add(row)
        session.flush()
    return row


def _naive(instant: datetime) -> datetime:
    """SQLite keeps no offset, so rows hold UTC wall time."""
    return instant.astimezone(UTC).replace(tzinfo=None)
