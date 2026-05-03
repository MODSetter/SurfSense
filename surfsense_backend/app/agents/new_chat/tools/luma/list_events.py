import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker

from ._auth import LUMA_API, get_api_key, get_luma_connector, luma_headers

logger = logging.getLogger(__name__)


def create_list_luma_events_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    """
    Factory function to create the list_luma_events tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker` so the closure is safe to share across
    HTTP requests by the compiled-agent cache. Capturing a per-request
    session here would surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.

    Returns:
        Configured list_luma_events tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def list_luma_events(
        max_results: int = 25,
    ) -> dict[str, Any]:
        """List upcoming and recent Luma events.

        Args:
            max_results: Maximum events to return (default 25, max 50).

        Returns:
            Dictionary with status and a list of events including
            event_id, name, start_at, end_at, location, url.
        """
        if search_space_id is None or user_id is None:
            return {"status": "error", "message": "Luma tool not properly configured."}

        max_results = min(max_results, 50)

        try:
            async with async_session_maker() as db_session:
                connector = await get_luma_connector(
                    db_session, search_space_id, user_id
                )
                if not connector:
                    return {"status": "error", "message": "No Luma connector found."}

                api_key = get_api_key(connector)
                headers = luma_headers(api_key)

                all_entries: list[dict] = []
                cursor = None

                async with httpx.AsyncClient(timeout=20.0) as client:
                    while len(all_entries) < max_results:
                        params: dict[str, Any] = {
                            "limit": min(100, max_results - len(all_entries))
                        }
                        if cursor:
                            params["cursor"] = cursor

                        resp = await client.get(
                            f"{LUMA_API}/calendar/list-events",
                            headers=headers,
                            params=params,
                        )

                        if resp.status_code == 401:
                            return {
                                "status": "auth_error",
                                "message": "Luma API key is invalid.",
                                "connector_type": "luma",
                            }
                        if resp.status_code != 200:
                            return {
                                "status": "error",
                                "message": f"Luma API error: {resp.status_code}",
                            }

                        data = resp.json()
                        entries = data.get("entries", [])
                        if not entries:
                            break
                        all_entries.extend(entries)

                        next_cursor = data.get("next_cursor")
                        if not next_cursor:
                            break
                        cursor = next_cursor

                events = []
                for entry in all_entries[:max_results]:
                    ev = entry.get("event", {})
                    geo = ev.get("geo_info", {})
                    events.append(
                        {
                            "event_id": entry.get("api_id"),
                            "name": ev.get("name", "Untitled"),
                            "start_at": ev.get("start_at", ""),
                            "end_at": ev.get("end_at", ""),
                            "timezone": ev.get("timezone", ""),
                            "location": geo.get("name", ""),
                            "url": ev.get("url", ""),
                            "visibility": ev.get("visibility", ""),
                        }
                    )

                return {"status": "success", "events": events, "total": len(events)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error listing Luma events: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to list Luma events."}

    return list_luma_events
