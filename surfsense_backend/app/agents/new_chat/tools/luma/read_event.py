import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker

from ._auth import LUMA_API, get_api_key, get_luma_connector, luma_headers

logger = logging.getLogger(__name__)


def create_read_luma_event_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    """
    Factory function to create the read_luma_event tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker` so the closure is safe to share across
    HTTP requests by the compiled-agent cache. Capturing a per-request
    session here would surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.

    Returns:
        Configured read_luma_event tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def read_luma_event(event_id: str) -> dict[str, Any]:
        """Read detailed information about a specific Luma event.

        Args:
            event_id: The Luma event API ID (from list_luma_events).

        Returns:
            Dictionary with status and full event details including
            description, attendees count, meeting URL.
        """
        if search_space_id is None or user_id is None:
            return {"status": "error", "message": "Luma tool not properly configured."}

        try:
            async with async_session_maker() as db_session:
                connector = await get_luma_connector(
                    db_session, search_space_id, user_id
                )
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
                    return {
                        "status": "auth_error",
                        "message": "Luma API key is invalid.",
                        "connector_type": "luma",
                    }
                if resp.status_code == 404:
                    return {
                        "status": "not_found",
                        "message": f"Event '{event_id}' not found.",
                    }
                if resp.status_code != 200:
                    return {
                        "status": "error",
                        "message": f"Luma API error: {resp.status_code}",
                    }

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
