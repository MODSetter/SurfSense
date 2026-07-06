"""``web.crawl`` executor: seeds → site spider → one cleaned item per fetched page.

Boundary owned elsewhere: the crawl frontier/fetch live in the proprietary engine
(``app.proprietary.web_crawler``). This executor only maps the engine's
``CrawlPage`` list onto the typed ``CrawlOutput`` (status labels, truncation, and
the captcha telemetry the billing seam reads).
"""

from __future__ import annotations

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.web.crawl.schemas import (
    ContactRef,
    Contacts,
    CrawlInput,
    CrawlItem,
    CrawlMeta,
    CrawlOutput,
    Link,
    SiteContacts,
)
from app.proprietary.web_crawler import (
    CrawlOutcomeStatus,
    CrawlPage,
    WebCrawlerConnector,
    crawl_site,
)

_STATUS_LABEL: dict[CrawlOutcomeStatus, str] = {
    CrawlOutcomeStatus.SUCCESS: "success",
    CrawlOutcomeStatus.EMPTY: "empty",
    CrawlOutcomeStatus.FAILED: "failed",
}


def build_crawl_executor(engine: WebCrawlerConnector | None = None) -> Executor:
    """Build the ``web.crawl`` executor, optionally over an injected engine (tests)."""
    crawler = engine or WebCrawlerConnector()

    async def execute(payload: CrawlInput) -> CrawlOutput:
        emit_progress(
            "starting",
            f"Crawling {len(payload.startUrls)} seed URL(s)",
            total=payload.maxCrawlPages,
            unit="page",
        )
        pages = await crawl_site(
            crawler,
            payload.startUrls,
            max_crawl_depth=payload.maxCrawlDepth,
            max_crawl_pages=payload.maxCrawlPages,
            include_patterns=payload.includeUrlPatterns,
            exclude_patterns=payload.excludeUrlPatterns,
        )
        emit_progress(
            "processing",
            f"Processing {len(pages)} crawled page(s)",
            current=len(pages),
            unit="page",
        )
        items = [_to_item(page, payload.maxLength) for page in pages]
        emit_progress("done", f"Crawled {len(items)} page(s)", current=len(items), unit="page")
        return CrawlOutput(
            items=items,
            contacts=_aggregate_contacts(items),
            captcha_attempts=sum(page.captcha_attempts for page in pages),
            captcha_solved=sum(1 for page in pages if page.captcha_solved),
        )

    return execute


def _to_item(page: CrawlPage, max_length: int) -> CrawlItem:
    content = page.content[:max_length] if page.content is not None else None
    contacts = Contacts(**page.contacts) if page.contacts else None
    return CrawlItem(
        url=page.url,
        status=_STATUS_LABEL[page.status],
        crawl=CrawlMeta(
            loadedUrl=page.loaded_url or page.url,
            depth=page.depth,
            referrerUrl=page.referrer,
        ),
        markdown=content,
        metadata=page.metadata,
        contacts=contacts,
        links=[Link(**record) for record in page.links or []],
        error=page.error,
    )


# Pages listed per contact value; the full list lives in the per-page items.
_MAX_REF_PAGES = 5


def _aggregate_contacts(items: list[CrawlItem]) -> SiteContacts:
    """Union each page's contacts with provenance (which pages, site-wide or not).

    ``siteWide`` marks values found on the majority of successfully parsed
    pages: on a multi-page crawl that's header/footer boilerplate — the
    company's own contacts — as opposed to page-local finds like one person's
    LinkedIn on the team page. ponytail: a single-page crawl can't tell the
    two apart, so everything is siteWide there; only page structure (footer
    detection) could do better.
    """
    pages_with_contacts = sum(1 for item in items if item.contacts is not None)
    threshold = max(2, pages_with_contacts / 2)

    def refs(values_by_page: dict[str, list[str]]) -> list[ContactRef]:
        return [
            ContactRef(
                value=value,
                pages=pages[:_MAX_REF_PAGES],
                pageCount=len(pages),
                siteWide=pages_with_contacts == 1 or len(pages) >= threshold,
            )
            for value, pages in values_by_page.items()
        ]

    emails: dict[str, list[str]] = {}
    phones: dict[str, list[str]] = {}
    socials: dict[str, list[str]] = {}
    for item in items:
        if item.contacts is None:
            continue
        for bucket, values in (
            (emails, item.contacts.emails),
            (phones, item.contacts.phones),
            (socials, item.contacts.socials),
        ):
            for value in values:
                bucket.setdefault(value, []).append(item.url)
    return SiteContacts(emails=refs(emails), phones=refs(phones), socials=refs(socials))
