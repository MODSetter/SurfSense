"""Asks the plugin host whether the license still unlocks the paid plugins, and applies it.

The host's answer is the only judge: the app's own license file says only when to ask.
Called on a license change, on opening Plugins, and before each agent turn.
"""

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress.service import EgressDeniedError, host_destination, require
from modules.license.service import status
from modules.plugins.license_verdict.applied_verdict import apply_verdict, paid_plugins
from modules.plugins.license_verdict.asked_verdict import asked_verdict
from modules.plugins.license_verdict.verdict_clock import CLOCK, now
from modules.plugins.lists.plugin_host import plugin_host
from modules.plugins.remote.sign_in.plugin_headers import license_headers


async def refresh_license_verdict(session: Session, *, if_stale: bool) -> list[str]:
    """The names of plugins it newly holds out; none when nothing was asked or answered."""
    headers = await transact(session, _planned, if_stale)
    if headers is None:
        return []
    verdict = await asked_verdict(headers)
    if verdict is None:
        return []
    answered_at = now()

    def apply(s: Session) -> list[str]:
        CLOCK.answered(answered_at)
        return apply_verdict(s, verdict.failure)

    return await transact(session, apply)


def _planned(session: Session, if_stale: bool) -> dict[str, str] | None:
    """None with no paid plugin, the host switched off in Settings > Network, or a fresh verdict."""
    if not paid_plugins(session):
        return None
    try:
        require(session, host_destination(plugin_host()))
    except EgressDeniedError:
        return None
    if if_stale and not CLOCK.due(now(), status(session).expiry):
        return None
    return license_headers(session, plugin_host())
