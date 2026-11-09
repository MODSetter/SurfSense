"""The day the plugin host first saw each licence, from its admin route."""

from __future__ import annotations

from datetime import date

import httpx2

_TIMEOUT_SECONDS = 30.0


async def read_first_seen(
    admin_url: str,
    token: str,
    *,
    client: httpx2.AsyncClient | None = None,
) -> dict[str, date]:
    """``{keygen licence id: first day seen}`` from ``GET /admin/usage/first-seen``."""
    url = f"{admin_url.rstrip('/')}/admin/usage/first-seen"
    headers = {"Authorization": f"Bearer {token}"}
    if client is None:
        async with httpx2.AsyncClient(timeout=_TIMEOUT_SECONDS) as owned:
            response = await owned.get(url, headers=headers)
    else:
        response = await client.get(url, headers=headers)
    response.raise_for_status()
    first_seen: dict[str, date] = {}
    for licence_id, day in (response.json().get("licences") or {}).items():
        try:
            first_seen[str(licence_id)] = date.fromisoformat(str(day))
        except ValueError:
            continue
    return first_seen
