"""The outcome of listing a plugin's server: its tools recorded, or why it could not be listed."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import (
    LICENSE_FAILURES,
    CheckFailure,
    InstalledPlugin,
)
from modules.plugins.installed.recorded_tools import record_tools
from modules.plugins.remote.connect_refusal import SIGN_IN_STATUSES
from modules.plugins.remote.mcp_client.server_error import ServerError


def record_check(
    session: Session, plugin: InstalledPlugin, listed: list[SourceTool] | ServerError
) -> None:
    """A failure keeps the tools last recorded: a server down for a minute changes none."""
    plugin.checked_at = datetime.now(UTC)
    if isinstance(listed, ServerError):
        failure = check_failure(listed)
        if listed.scopes:
            # Signing in again asks for them: Needs more access, not Signed out.
            auth = plugin.entry.get("auth", {})
            plugin.entry = {
                **plugin.entry,
                "auth": {**auth, "needs_scopes": listed.scopes},
            }
        # No answer is no news: a server out of reach, or Keygen down, keeps a license verdict.
        if not (
            failure == CheckFailure.UNREACHABLE
            and plugin.check_failure in LICENSE_FAILURES
        ):
            plugin.check_failure = failure
        session.flush()
        return
    plugin.check_failure = None
    record_tools(session, plugin, listed)


# Contract 2's reasons. Keygen unreachable, `license_service_unavailable`, is temporary.
LICENSE_REFUSALS = {
    "missing_license": CheckFailure.NEEDS_LICENSE,
    "expired": CheckFailure.LICENSE_EXPIRED,
    "revoked": CheckFailure.LICENSE_REVOKED,
    "invalid": CheckFailure.LICENSE_INVALID,
}


def check_failure(error: ServerError) -> CheckFailure:
    if error.status in SIGN_IN_STATUSES:
        return LICENSE_REFUSALS.get(error.reason or "", CheckFailure.SIGN_IN)
    return CheckFailure.UNREACHABLE
