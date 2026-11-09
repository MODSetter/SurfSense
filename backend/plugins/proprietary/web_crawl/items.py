"""A crawled page as the tool returns it, in the backend capability's wire shape."""

from typing import Any

from proprietary.web_crawl.connector import CrawlOutcomeStatus
from proprietary.web_crawl.site_crawler import CrawlPage

_STATUS_LABEL: dict[CrawlOutcomeStatus, str] = {
    CrawlOutcomeStatus.SUCCESS: "success",
    CrawlOutcomeStatus.EMPTY: "empty",
    CrawlOutcomeStatus.FAILED: "failed",
}


# Contact values kept per list; a page listing more is a directory, counted.
MAX_CONTACTS = 50


def _capped_contacts(
    contacts: dict[str, list[str]] | None,
) -> tuple[dict[str, list[str]] | None, dict[str, int] | None]:
    """Each contact list cut at ``MAX_CONTACTS``, and each list's full length."""
    if contacts is None:
        return None, None
    return (
        {kind: values[:MAX_CONTACTS] for kind, values in contacts.items()},
        {kind: len(values) for kind, values in contacts.items()},
    )


def crawl_item(
    page: CrawlPage, max_length: int, max_links: int | None = None
) -> dict[str, Any]:
    """``markdown`` is cut at ``max_length`` characters, ``links`` at ``max_links``
    and each contact list at ``MAX_CONTACTS``; the totals say what was cut.
    """
    links = list(page.links or [])
    links_total = max(page.links_total or 0, len(links))
    if max_links is not None:
        links = links[:max_links]
    contacts, contacts_total = _capped_contacts(page.contacts)
    return {
        "url": page.url,
        "status": _STATUS_LABEL[page.status],
        "crawl": {
            "loadedUrl": page.loaded_url or page.url,
            "depth": page.depth,
            "referrerUrl": page.referrer,
        },
        "markdown": page.content[:max_length] if page.content is not None else None,
        "metadata": page.metadata,
        "contacts": contacts,
        "contactsTotal": contacts_total,
        "links": links,
        "linksTotal": links_total,
        "linksTruncated": links_total > len(links),
        "error": page.error,
    }
