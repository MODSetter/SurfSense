"""The imported license's key, which SurfSense's paid plugins send to their server."""

from sqlalchemy.orm import Session

from modules.license.models import LicenseState
from modules.license.verify import verify_signature


def license_key(session: Session) -> str | None:
    """None with no license imported. Expiry is the server's to judge, never the app's."""
    row = session.get(LicenseState, 1)
    if row is None or row.certificate is None:
        return None
    return verify_signature(row.certificate).key
