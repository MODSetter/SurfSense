"""The hosts a click in Add from the web reaches, asked about in one question (ADR 0060).

Adding links asks about every host their reads start on; Retry also asks about the
host a site moved the page to, which the pull could only name once it was sent there.
Search asks about the SearXNG server's host.
"""

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from modules.documents.models import Document
from modules.documents.web_sources.background_pull.source_link import (
    MOVED_TO,
    SOURCE_URL,
)
from modules.documents.web_sources.links import routed
from modules.egress.service import EgressDeniedError
from modules.plugins.installed.plugin_hosts import refused_hosts

# What the consent prompt words its question by.
WEB_PAGE = "web_page"
WEB_SEARCH = "web_search"


def refused_link_hosts(session: Session, urls: list[str]) -> EgressDeniedError | None:
    hosts = [host for url in urls for host in routed(url).hosts(url)]
    return refused_hosts(session, hosts, purpose=WEB_PAGE)


def refused_pull_hosts(
    session: Session, document: Document
) -> EgressDeniedError | None:
    """For Retry: the link's hosts, and the one its last pull was moved to."""
    metadata = document.document_metadata or {}
    url = metadata[SOURCE_URL]
    hosts = routed(url).hosts(url)
    if moved_to := metadata.get(MOVED_TO):
        hosts.append(moved_to)
    return refused_hosts(session, hosts, purpose=WEB_PAGE)


def refused_search_host(session: Session, server: str) -> EgressDeniedError | None:
    return refused_hosts(session, [urlsplit(server).hostname or ""], purpose=WEB_SEARCH)
