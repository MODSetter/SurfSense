"""Any link no other puller takes: the page's text, read by Web Crawl."""

from urllib.parse import SplitResult

from modules.documents.web_sources.pullers.puller import (
    Fit,
    Pulled,
    Puller,
    Results,
    ToolCall,
)

# Far above an article, so a long page is kept whole; Web Crawl's default is 50,000.
MAX_CHARACTERS = 1_000_000


def _fit(_: SplitResult) -> Fit:
    return Fit.ONE


def _calls(url: str) -> list[ToolCall]:
    """This page only: no link followed, and a source needs none of its links."""
    return [
        ToolCall(
            "crawl",
            {
                "start_urls": [url],
                "max_crawl_depth": 0,
                "max_crawl_pages": 1,
                "max_length": MAX_CHARACTERS,
                "max_links": 0,
            },
        )
    ]


def _written(url: str, results: Results) -> Pulled | None:
    page = next(iter(results.get("crawl") or []), None)
    if page is None or page.get("status") != "success":
        return None
    markdown = (page.get("markdown") or "").strip()
    if not markdown:
        return None
    title = (page.get("metadata") or {}).get("title") or url
    return Pulled(title, markdown)


PULLER = Puller(
    id="web_page", plugin_id="web-crawl", fit=_fit, calls=_calls, written=_written
)
