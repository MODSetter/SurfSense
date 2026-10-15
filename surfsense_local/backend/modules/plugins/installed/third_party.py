"""Whether the user allowed third-party plugins: every publisher's but SurfSense's."""

from sqlalchemy.orm import Session

from modules.plugins.installed.models import PluginSettings

# The table's one row; the database refuses any other id.
SETTINGS_ROW = 1


def third_party_on(session: Session) -> bool:
    settings = session.get(PluginSettings, SETTINGS_ROW)
    return settings is not None and settings.third_party_on


def set_third_party_on(session: Session, on: bool) -> None:
    settings = session.get(PluginSettings, SETTINGS_ROW)
    if settings is None:
        settings = PluginSettings(id=SETTINGS_ROW)
        session.add(settings)
    settings.third_party_on = on
    session.flush()
