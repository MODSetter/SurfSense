"""Which SearXNG server a search asks: the user's choice, else SurfSense's hosted one."""

from sqlalchemy.orm import Session

from modules.documents.web_sources.web_search.models import WebSearchSettings

# SurfSense's own instance, which the plugin host's Google Search also falls back to.
DEFAULT_SEARCH_SERVER = "https://searxng.surfsense.com"
# The table's one row; the database refuses any other id.
SETTINGS_ROW = 1


def chosen_search_server(session: Session) -> str | None:
    settings = session.get(WebSearchSettings, SETTINGS_ROW)
    return settings.searxng_url if settings is not None else None


def search_server(session: Session) -> str:
    return chosen_search_server(session) or DEFAULT_SEARCH_SERVER


def choose_search_server(session: Session, url: str | None) -> None:
    """None goes back to SurfSense's."""
    settings = session.get(WebSearchSettings, SETTINGS_ROW)
    if settings is None:
        settings = WebSearchSettings(id=SETTINGS_ROW)
        session.add(settings)
    settings.searxng_url = url
    session.flush()
