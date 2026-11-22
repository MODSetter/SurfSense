"""A link as a row the dialog shows: its site, and the puller that would take it."""

from urllib.parse import urlsplit

from modules.documents.web_sources.links import routed
from modules.documents.web_sources.schemas import WebResult


def result_row(url: str, title: str | None, description: str | None) -> WebResult:
    return WebResult(
        url=url,
        title=title or url,
        description=description or None,
        site=urlsplit(url).hostname or url,
        puller=routed(url).id,
    )
