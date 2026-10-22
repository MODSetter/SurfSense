"""A link as a row the dialog shows: its site, the puller that would take it, and how."""

from urllib.parse import urlsplit

from modules.documents.web_sources.links import routed
from modules.documents.web_sources.schemas import WebResult


def result_row(url: str, title: str | None, description: str | None) -> WebResult:
    route = routed(url)
    return WebResult(
        url=url,
        title=title or url,
        description=description or None,
        site=urlsplit(url).hostname or url,
        puller=route.puller.id,
        fit=route.fit,
    )
