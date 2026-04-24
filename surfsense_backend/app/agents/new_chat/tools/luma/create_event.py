import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval

from ._auth import LUMA_API, get_api_key, get_luma_connector, luma_headers

logger = logging.getLogger(__name__)


def create_create_luma_event_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_luma_event(
        name: str,
        start_at: str,
        end_at: str,
        description: str | None = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """Create a new event on Luma.

        Args:
            name: The event title.
            start_at: Start time in ISO 8601 format (e.g. "2026-05-01T18:00:00").
            end_at: End time in ISO 8601 format (e.g. "2026-05-01T20:00:00").
            description: Optional event description (markdown supported).
            timezone: Timezone string (default "UTC", e.g. "America/New_York").

        Returns:
            Dictionary with status, event_id on success.

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Do NOT retry.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Luma tool not properly configured."}

        try:
            connector = await get_luma_connector(db_session, search_space_id, user_id)
            if not connector:
                return {"status": "error", "message": "No Luma connector found."}

            result = request_approval(
                action_type="luma_create_event",
                tool_name="create_luma_event",
                params={
                    "name": name,
                    "start_at": start_at,
                    "end_at": end_at,
                    "description": description,
                    "timezone": timezone,
                },
                context={"connector_id": connector.id},
            )

            if result.rejected:
                return {"status": "rejected", "message": "User declined. Event was not created."}

            final_name = result.params.get("name", name)
            final_start = result.params.get("start_at", start_at)
            final_end = result.params.get("end_at", end_at)
            final_desc = result.params.get("description", description)
            final_tz = result.params.get("timezone", timezone)

            api_key = get_api_key(connector)
            headers = luma_headers(api_key)

            body: dict[str, Any] = {
                "name": final_name,
                "start_at": final_start,
                "end_at": final_end,
                "timezone": final_tz,
            }
            if final_desc:
                body["description_md"] = final_desc

            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{LUMA_API}/event/create",
                    headers=headers,
                    json=body,
                )

            if resp.status_code == 401:
                return {"status": "auth_error", "message": "Luma API key is invalid.", "connector_type": "luma"}
            if resp.status_code == 403:
                return {"status": "error", "message": "Luma Plus subscription required to create events via API."}
            if resp.status_code not in (200, 201):
                return {"status": "error", "message": f"Luma API error: {resp.status_code} — {resp.text[:200]}"}

            data = resp.json()
            event_id = data.get("api_id") or data.get("event", {}).get("api_id")

            return {
                "status": "success",
                "event_id": event_id,
                "message": f"Event '{final_name}' created on Luma.",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error creating Luma event: %s", e, exc_info=True)
            return {"status": "error", "message": "Failed to create Luma event."}

    return create_luma_event
