"""The outcome of listing a plugin's server: its tools recorded, or why it could not be listed."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import CheckFailure, InstalledPlugin
from modules.plugins.installed.recorded_tools import record_tools
from modules.plugins.remote.connect_refusal import SIGN_IN_STATUSES
from modules.plugins.remote.mcp_client.server_error import ServerError


def record_check(
    session: Session, plugin: InstalledPlugin, listed: list[SourceTool] | ServerError
) -> None:
    """A failure keeps the tools last recorded: a server down for a minute changes none."""
    plugin.checked_at = datetime.now(UTC)
    if isinstance(listed, ServerError):
        plugin.check_failure = check_failure(listed)
        session.flush()
        return
    plugin.check_failure = None
    record_tools(session, plugin, listed)


# Contract 2's reasons. Keygen unreachable, `license_service_unavailable`, is temporary.
_LICENSE_REFUSALS = {
    "missing_license": CheckFailure.NEEDS_LICENSE,
    "expired": CheckFailure.LICENSE_EXPIRED,
    "revoked": CheckFailure.LICENSE_REVOKED,
    "invalid": CheckFailure.LICENSE_INVALID,
}


def check_failure(error: ServerError) -> CheckFailure:
    if error.status in SIGN_IN_STATUSES:
        return _LICENSE_REFUSALS.get(error.reason or "", CheckFailure.SIGN_IN)
    return CheckFailure.UNREACHABLE
