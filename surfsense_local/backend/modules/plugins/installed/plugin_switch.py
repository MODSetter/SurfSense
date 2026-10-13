"""The user's switch on a whole plugin: off pauses it, keeping its sign-in and tool choices."""

from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin


def set_plugin_enabled(
    session: Session, plugin_id: str, enabled: bool
) -> InstalledPlugin | None:
    """None when no such plugin is connected."""
    plugin = session.get(InstalledPlugin, plugin_id)
    if plugin is None:
        return None
    plugin.enabled = enabled
    session.flush()
    return plugin
