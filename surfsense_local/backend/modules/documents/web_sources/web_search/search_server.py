"""Which SearXNG server a search asks: the user's choice. There is no default (ADR 0092), so
search is off until the user names one; reading a link they give needs no server."""

from sqlalchemy.orm import Session

from modules.documents.web_sources.web_search.models import WebSearchSettings

# The table's one row; the database refuses any other id.
SETTINGS_ROW = 1


def search_server(session: Session) -> str | None:
    """None while the user has named no server: no search is sent anywhere."""
    settings = session.get(WebSearchSettings, SETTINGS_ROW)
    return settings.searxng_url if settings is not None else None


def choose_search_server(session: Session, url: str | None) -> None:
    """None turns search off again."""
    settings = session.get(WebSearchSettings, SETTINGS_ROW)
    if settings is None:
        settings = WebSearchSettings(id=SETTINGS_ROW)
        session.add(settings)
    settings.searxng_url = url
    session.flush()
