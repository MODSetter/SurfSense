"""User-search flow: keyword -> public account records.

Unlike video/general search (login-walled for anonymous sessions), the Users tab
hits ``/api/search/user`` and returns account records without a redirect. Each
query's results are deduped by uid, capped, and — when a query returns nothing —
degraded to one ErrorItem, mirroring the listing flow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from ..extraction import parse_search_user
from ..extraction.timestamps import now_iso
from ..schemas import ErrorItem
from . import FetchUsersFn

_USER_SEARCH_URL = "https://www.tiktok.com/search/user?q={query}"
_EMPTY_MESSAGE = (
    "No accounts returned for this query. It may have no matches, or TikTok "
    "withheld the results from anonymous access."
)


async def iter_user_search(
    query: str, *, cap: int, fetch_users: FetchUsersFn
) -> AsyncIterator[dict[str, Any]]:
    if cap <= 0:
        return
    url = _USER_SEARCH_URL.format(query=quote(query))
    seen: set[str] = set()
    emitted = 0
    for user_info in await fetch_users(url, cap):
        out = parse_search_user(user_info)
        uid = out.get("id")
        if uid is not None:
            if uid in seen:
                continue
            seen.add(uid)
        out["scrapedAt"] = now_iso()
        yield out
        emitted += 1
        if emitted >= cap:
            return
    if emitted == 0:
        yield ErrorItem(
            url=url,
            input=query,
            error=_EMPTY_MESSAGE,
            errorCode="no_users",
            scrapedAt=now_iso(),
        ).to_output()
