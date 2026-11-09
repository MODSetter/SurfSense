"""A page or a transcript read from the web, a page of lines at a time, as read_document pages a script."""

from modules.agent.tool_endpoint.script_page import OffsetOutOfRangeError, page_of
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.documents.web_sources.pullers.puller import Pulled


def web_text_page(pulled: Pulled, url: str, offset: object, tool: str) -> str:
    """Its title, its link, which lines these are, then the lines."""
    if offset is None:
        offset = 1
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise ToolCallError("offset is a line number, 1 for the first.")
    try:
        page = page_of(pulled.markdown, offset)
    except OffsetOutOfRangeError as error:
        lines = len(pulled.markdown.splitlines()) or 1
        raise ToolCallError(
            f"The text has {lines} lines: give an offset from 1 to {lines}, or "
            "leave it out to start at the top."
        ) from error
    where = f"Lines {page.first}-{page.last} of {page.total}."
    if page.last < page.total:
        where += f" Call {tool} again with offset {page.last + 1} for the rest."
    return f"Title: {pulled.title}\nLink: {url}\n{where}\n\n{page.text}"
