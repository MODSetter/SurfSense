"""A search on the web or on YouTube, as the rows the dialog shows."""

from pydantic import TypeAdapter, ValidationError

from modules.documents.web_sources.pullers import youtube
from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.schemas import WebLink, WebResults
from modules.documents.web_sources.web_search.searxng import searxng_page

# Pages a search shows at most, Show more asking for each.
MAX_PAGES = 5
# A row is a link Add takes: one Add refuses would fail Add all's whole batch.
_ADDABLE = TypeAdapter(WebLink)


async def search_rows(server: str, query: str, source: str, page: int) -> WebResults:
    """YouTube's search is the web's, kept to its videos: those come with a transcript."""
    asked = f"{query} site:youtube.com" if source == youtube.PULLER.id else query
    found = await searxng_page(server, asked, page)
    rows = [result_row(f.url, f.title, f.description) for f in found if _addable(f.url)]
    if source == youtube.PULLER.id:
        rows = [row for row in rows if row.puller == youtube.PULLER.id]
    return WebResults(results=rows, more=bool(found) and page + 1 < MAX_PAGES)


def _addable(url: str) -> bool:
    try:
        _ADDABLE.validate_python(url)
    except ValidationError:
        return False
    return True
