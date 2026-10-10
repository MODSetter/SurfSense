"""Disconnecting a plugin: its credentials and tools go, its past calls stay in their threads.

The cascade is the database's: both tables reference `installed_plugins`, and
`plugin_calls` deliberately does not.
"""

from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin


def disconnect(session: Session, plugin_id: str) -> bool:
    """False when no such plugin is connected."""
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is None:
        return False
    session.delete(plugin)
    session.flush()
    return True
