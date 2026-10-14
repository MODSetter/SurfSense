"""The plugin host's verdict on the imported license, asked once for every paid plugin."""

from dataclasses import dataclass

import httpx2

from modules.plugins.installed.models import CheckFailure
from modules.plugins.installed.plugin_check import LICENSE_REFUSALS
from modules.plugins.lists.plugin_host import plugin_host

TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class Verdict:
    """None: the license unlocks the paid plugins."""

    failure: CheckFailure | None


class RouteMissing:
    """A plugin host built before `/license`: the verdict comes from one listing instead."""


async def asked_verdict(headers: dict[str, str]) -> Verdict | RouteMissing | None:
    """None when the host gave no verdict: unreachable, Keygen down, or an answer it never sends."""
    try:
        async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
            answer = await http.get(f"{plugin_host()}/license", headers=headers)
    except httpx2.HTTPError:
        return None
    if answer.status_code == 404:
        return RouteMissing()
    if answer.status_code == 200:
        return Verdict(None)
    if answer.status_code in (401, 403):
        try:
            reason = answer.json().get("reason")
        except ValueError:
            return None
        failure = LICENSE_REFUSALS.get(reason)
        return Verdict(failure) if failure else None
    return None
