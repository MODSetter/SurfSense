"""While third-party plugins are off, nothing reaches a third-party plugin's server."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin, PluginSource
from modules.plugins.installed.third_party import third_party_on


def third_party_refusal(session: Session, source: str) -> HTTPException | None:
    """The switch's consent covers every request to another publisher's server."""
    if source == PluginSource.FIRST_PARTY or third_party_on(session):
        return None
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        {
            "code": "third_party_off",
            "message": "Allow third-party plugins to connect this one.",
        },
    )


def plugin_third_party_refusal(
    session: Session, plugin_id: str
) -> HTTPException | None:
    """For a saved plugin; one not found is left to the route's own 404."""
    plugin = session.get(InstalledPlugin, plugin_id)
    return None if plugin is None else third_party_refusal(session, plugin.source)
