"""A list's items, 20 at a time, read by its puller's plugin as rows to pick from: a list
link's, or a site's own search for a query.

Plugins take a count, not an offset, so page 2 asks for 60 and shows the last 20. A list
shows at most 100 items: the most several plugins return in one call.
"""

from collections.abc import Callable

from modules.documents.web_sources.plugin_calls.plugin_access import PluginAccess
from modules.documents.web_sources.plugin_calls.plugin_call import (
    PluginUnavailableError,
    ToolRefusedError,
    call_plugin,
)
from modules.documents.web_sources.pullers.puller import Listing, ToolCall
from modules.documents.web_sources.rows.result_rows import result_row
from modules.documents.web_sources.schemas import WebGroup

PAGE = 20
MAX_LISTED = 100
# A list is read while the user waits: a channel or a search page, not a whole crawl.
LIST_SECONDS = 300


async def read_page(
    access: PluginAccess,
    call_for: Callable[[int], ToolCall],
    listing: Listing,
    page: int,
    link: str | None,
) -> WebGroup:
    """Raises what the plugin call raises; `call_for` takes how many items to read."""
    count = min((page + 1) * PAGE, MAX_LISTED)
    call = call_for(count)
    items = await call_plugin(access, call.tool, call.arguments, LIST_SECONDS)
    listed = listing.items(items)
    shown = listed[page * PAGE : count]
    return WebGroup(
        link=link,
        results=[result_row(i.url, i.title, i.description) for i in shown],
        more=len(listed) >= count and count < MAX_LISTED,
        failed=False,
    )


async def list_page(
    access: PluginAccess, listing: Listing, url: str, page: int
) -> WebGroup:
    """A list that cannot be read comes back failed, so the rest of a paste still opens."""
    try:
        return await read_page(
            access, lambda count: listing.call(url, count), listing, page, url
        )
    except (PluginUnavailableError, ToolRefusedError):
        return WebGroup(link=url, results=[], more=False, failed=True)
