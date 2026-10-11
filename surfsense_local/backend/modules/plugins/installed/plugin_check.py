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
        plugin.check_failure = (
            CheckFailure.SIGN_IN
            if listed.status in SIGN_IN_STATUSES
            else CheckFailure.UNREACHABLE
        )
        session.flush()
        return
    plugin.check_failure = None
    record_tools(session, plugin, listed)
