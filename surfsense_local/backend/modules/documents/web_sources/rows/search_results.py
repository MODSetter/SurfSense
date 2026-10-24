"""Google's results page as links to pick: organic results only, each link once."""

from typing import Any

from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.schemas import WebResult

GOOGLE_SEARCH = "google-search"
SCRAPE = "scrape"


# Google pages a search shows at most, about ten links each.
MAX_PAGES = 5


def search_arguments(query: str, page: int) -> dict[str, Any]:
    """Every results page up to this one: the plugin starts each search at page 1."""
    return {"queries": [query], "max_pages_per_query": page + 1}


def listed_results(items: list[dict[str, Any]]) -> list[WebResult]:
    """Ads, related questions and the AI Overview are not pages to add."""
    results: list[WebResult] = []
    seen: set[str] = set()
    for page in items:
        for organic in page.get("organicResults") or []:
            url = organic.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            results.append(
                result_row(url, organic.get("title"), organic.get("description"))
            )
    return results
