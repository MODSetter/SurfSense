"""Fetches the stored license's renewed file and imports it in its place.

Contract 1's consumer rules 7 and 8. Settings' button and the app's own daily
check both come through here.
"""

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress.service import EgressDeniedError, refused_named_host
from modules.license.license_key import license_key
from modules.license.renewal.license_server import license_server
from modules.license.renewal.refresh_failed import RefreshFailedError
from modules.license.renewal.renewed_file import renewed_file
from modules.license.service import LicenseStatus, import_certificate, status
from modules.license.verify import verify_signature

# The consent question words itself by this when the host alone does not say,
# as for a firm's mirror.
PURPOSE = "license_refresh"


async def refresh_license(session: Session) -> LicenseStatus:
    """The new status. Raises RefreshFailedError, or LicenseRejectedError with the
    code `PUT /license` would answer for the same file."""
    server = license_server()
    planned = await transact(session, _planned, server)
    if isinstance(planned, EgressDeniedError):
        raise RefreshFailedError("refresh_egress_blocked", planned)
    certificate = await renewed_file(server, planned)
    return await transact(session, _replaced, planned, certificate)


def _planned(session: Session, server: str) -> str | EgressDeniedError:
    """The key to send, or the refusal, returned so the commit keeps a mirror's row for Settings."""
    key = license_key(session)
    if key is None:
        raise RefreshFailedError("license_none")
    refused = refused_named_host(session, server)
    if refused is not None:
        refused.purpose = PURPOSE
        return refused
    return key


def _replaced(session: Session, key: str, certificate: str) -> LicenseStatus:
    """Rule 7 matches on the key: the file takes the place of that license's file only."""
    # Read again, not from this session's last look: the fetch took seconds.
    session.expire_all()
    if license_key(session) != key:
        # Removed or replaced while the file was on its way: the user's choice stands.
        return status(session)
    if verify_signature(certificate).key != key:
        raise RefreshFailedError("refresh_unavailable")
    return import_certificate(session, certificate)
