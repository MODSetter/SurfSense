"""Removing a plugin: its row goes, its encrypted sign-in and its tools with it.

The cascade is the database's: `plugin_tools` references `installed_plugins`.
"""

from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin


def remove(session: Session, plugin_id: str) -> bool:
    """False when no such plugin is connected."""
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is None:
        return False
    session.delete(plugin)
    session.flush()
    return True
