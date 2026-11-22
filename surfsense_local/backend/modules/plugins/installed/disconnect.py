"""Disconnecting a plugin: its sign-in goes, the row and the user's tool settings stay.

`credential_kind` stays too, so the screen knows whether connecting again needs a key,
an account sign-in, or nothing.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin


def disconnect(session: Session, plugin_id: str) -> InstalledPlugin | None:
    """None when no such plugin is connected."""
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is None:
        return None
    plugin.credential = None
    plugin.disconnected_at = datetime.now(UTC)
    session.flush()
    return plugin
