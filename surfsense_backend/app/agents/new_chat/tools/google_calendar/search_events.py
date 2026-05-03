import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.new_chat.tools.gmail.search_emails import _build_credentials
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)

_CALENDAR_TYPES = [
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
]


def _to_calendar_boundary(value: str, *, is_end: bool) -> str:
    if "T" in value:
        return value
    time = "23:59:59" if is_end else "00:00:00"
    return f"{value}T{time}Z"


def _format_calendar_events(events_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for ev in events_raw:
        start = ev.get("start", {})
        end = ev.get("end", {})
        attendees_raw = ev.get("attendees", [])
        events.append(
            {
                "event_id": ev.get("id"),
                "summary": ev.get("summary", "No Title"),
                "start": start.get("dateTime") or start.get("date", ""),
                "end": end.get("dateTime") or end.get("date", ""),
                "location": ev.get("location", ""),
                "description": ev.get("description", ""),
                "html_link": ev.get("htmlLink", ""),
                "attendees": [a.get("email", "") for a in attendees_raw[:10]],
                "status": ev.get("status", ""),
            }
        )
    return events


def create_search_calendar_events_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def search_calendar_events(
        start_date: str,
        end_date: str,
        max_results: int = 25,
    ) -> dict[str, Any]:
        """Search Google Calendar events within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (e.g. "2026-04-01").
            end_date: End date in YYYY-MM-DD format (e.g. "2026-04-30").
            max_results: Maximum number of events to return (default 25, max 50).

        Returns:
            Dictionary with status and a list of events including
            event_id, summary, start, end, location, attendees.
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Calendar tool not properly configured.",
            }

        max_results = min(max_results, 50)

        try:
            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type.in_(_CALENDAR_TYPES),
                )
            )
            connector = result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "No Google Calendar connector found. Please connect Google Calendar in your workspace settings.",
                }

            if (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
            ):
                cca_id = connector.config.get("composio_connected_account_id")
                if not cca_id:
                    return {
                        "status": "error",
                        "message": "Composio connected account ID not found for this connector.",
                    }

                from app.services.composio_service import ComposioService

                events_raw, error = await ComposioService().get_calendar_events(
                    connected_account_id=cca_id,
                    entity_id=f"surfsense_{user_id}",
                    time_min=_to_calendar_boundary(start_date, is_end=False),
                    time_max=_to_calendar_boundary(end_date, is_end=True),
                    max_results=max_results,
                )
                if not events_raw and not error:
                    error = "No events found in the specified date range."
            else:
                creds = _build_credentials(connector)

                from app.connectors.google_calendar_connector import (
                    GoogleCalendarConnector,
                )

                cal = GoogleCalendarConnector(
                    credentials=creds,
                    session=db_session,
                    user_id=user_id,
                    connector_id=connector.id,
                )

                events_raw, error = await cal.get_all_primary_calendar_events(
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results,
                )

            if error:
                if (
                    "re-authenticate" in error.lower()
                    or "authentication failed" in error.lower()
                ):
                    return {
                        "status": "auth_error",
                        "message": error,
                        "connector_type": "google_calendar",
                    }
                if "no events found" in error.lower():
                    return {
                        "status": "success",
                        "events": [],
                        "total": 0,
                        "message": error,
                    }
                return {"status": "error", "message": error}

            events = _format_calendar_events(events_raw)

            return {"status": "success", "events": events, "total": len(events)}

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error("Error searching calendar events: %s", e, exc_info=True)
            return {
                "status": "error",
                "message": "Failed to search calendar events. Please try again.",
            }

    return search_calendar_events
