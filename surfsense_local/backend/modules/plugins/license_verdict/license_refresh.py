"""Asks the plugin host whether the license still unlocks the paid plugins, and applies it.

The host's answer is the only judge: the app's own license file says only when to ask.
Called on a license change, on opening Plugins, and before each agent turn.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.egress.service import EgressDeniedError, host_destination, require
from modules.license.service import status
from modules.plugins.installed.models import LICENSE_FAILURES
from modules.plugins.installed.plugin_check import check_failure
from modules.plugins.license_verdict.applied_verdict import apply_verdict, paid_plugins
from modules.plugins.license_verdict.asked_verdict import (
    RouteMissing,
    Verdict,
    asked_verdict,
)
from modules.plugins.license_verdict.verdict_clock import CLOCK, now
from modules.plugins.lists.plugin_host import plugin_host
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.sign_in.oauth.listed_after_refresh import list_once
from modules.plugins.remote.sign_in.plugin_headers import (
    license_headers,
    sign_in_headers,
)


@dataclass(frozen=True)
class _Ask:
    headers: dict[str, str]
    # A paid plugin to list instead, on a host built before `/license`.
    fallback: tuple[str, dict[str, str]]


async def refresh_license_verdict(session: Session, *, if_stale: bool) -> list[str]:
    """The names of plugins it newly holds out; none when nothing was asked or answered."""
    ask = await transact(session, _planned, if_stale)
    if ask is None:
        return []
    verdict = await asked_verdict(ask.headers)
    if isinstance(verdict, RouteMissing):
        verdict = _from_listing(await list_once(*ask.fallback))
    if verdict is None:
        return []
    answered_at = now()

    def apply(s: Session) -> list[str]:
        CLOCK.answered(answered_at)
        return apply_verdict(s, verdict.failure)

    return await transact(session, apply)


def _planned(session: Session, if_stale: bool) -> _Ask | None:
    """None with no paid plugin, the host switched off in Settings > Network, or a fresh verdict."""
    plugins = paid_plugins(session)
    if not plugins:
        return None
    try:
        require(session, host_destination(plugin_host()))
    except EgressDeniedError:
        return None
    if if_stale and not CLOCK.due(now(), status(session).expiry):
        return None
    first = plugins[0]
    return _Ask(
        license_headers(session, plugin_host()),
        (first.url, sign_in_headers(session, first)),
    )


def _from_listing(listed: list | ServerError) -> Verdict | None:
    if not isinstance(listed, ServerError):
        return Verdict(None)
    failure = check_failure(listed)
    return Verdict(failure) if failure in LICENSE_FAILURES else None
