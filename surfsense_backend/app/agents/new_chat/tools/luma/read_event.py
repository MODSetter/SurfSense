import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from ._auth import LUMA_API, get_api_key, get_luma_connector, luma_headers

logger = logging.getLogger(__name__)


def create_read_luma_event_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def read_luma_event(event_id: str) -> dict[str, Any]:
        """Read detailed information about a specific Luma event.

        Args:
            event_id: The Luma event API ID (from list_luma_events).

        Returns:
            Dictionary with status and full event details including
            description, attendees count, meeting URL.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Luma tool not properly configured."}

        try:
            connector = await get_luma_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Luma connector found."}

            api_key = get_api_key(connector)
            headers = luma_headers(api_key)

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{LUMA_API}/events/{event_id}",
                    headers=headers,
                )

            if resp.status_code == 401:
                return {"status": "auth_error", "message": "Luma API key is invalid.", "connector_type": "luma"}
            if resp.status_code == 404:
                return {"status": "not_found", "message": f"Event '{event_id}' not found."}
            if resp.status_code != 200:
                return {"status": "error", "message": f"Luma API error: {resp.status_code}"}

            data = resp.json()
            ev = data.get("event", data)
            geo = ev.get("geo_info", {})

            event_detail = {
                "event_id": event_id,
                "name": ev.get("name", ""),
                "description": ev.get("description", ""),
                "start_at": ev.get("start_at", ""),
                "end_at": ev.get("end_at", ""),
                "timezone": ev.get("timezone", ""),
                "location_name": geo.get("name", ""),
                "address": geo.get("address", ""),
                "url": ev.get("url", ""),
                "meeting_url": ev.get("meeting_url", ""),
                "visibility": ev.get("visibility", ""),
                "cover_url": ev.get("cover_url", ""),
            }

            return {"status": "success", "event": event_detail}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error reading Luma event: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to read Luma event."}

    return read_luma_event
