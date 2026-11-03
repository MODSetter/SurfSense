"""A search on the web or on YouTube, as the rows the dialog shows."""

from modules.documents.web_sources.pullers import youtube
from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.schemas import WebResults
from modules.documents.web_sources.web_search.searxng import searxng_page

# Pages a search shows at most, Show more asking for each.
MAX_PAGES = 5


async def search_rows(server: str, query: str, source: str, page: int) -> WebResults:
    """YouTube's search is the web's, kept to its videos: those come with a transcript."""
    asked = f"{query} site:youtube.com" if source == youtube.PULLER.id else query
    found = await searxng_page(server, asked, page)
    rows = [result_row(f.url, f.title, f.description) for f in found]
    if source == youtube.PULLER.id:
        rows = [row for row in rows if row.puller == youtube.PULLER.id]
    return WebResults(results=rows, more=bool(found) and page + 1 < MAX_PAGES)
