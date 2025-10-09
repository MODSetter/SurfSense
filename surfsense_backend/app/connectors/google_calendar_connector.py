"""
Google Calendar Connector Module | Google OAuth Credentials | Google Calendar API
A module for retrieving calendar events from Google Calendar using Google OAuth credentials.
Allows fetching events from specified calendars within date ranges using Google OAuth credentials.
"""

import json
from datetime import datetime
from typing import Any

import pytz
from dateutil.parser import isoparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
)


class GoogleCalendarConnector:
    """Class for retrieving data from Google Calendar using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        session: AsyncSession,
        user_id: str,
        connector_id: int | None = None,
    ):
        """
        Initialize the GoogleCalendarConnector class.
        Args:
            credentials: Google OAuth Credentials object
            session: Database session for updating connector
            user_id: User ID (kept for backward compatibility)
            connector_id: Optional connector ID for direct updates
        """
        self._credentials = credentials
        self._session = session
        self._user_id = user_id
        self._connector_id = connector_id
        self.service = None

    async def _get_credentials(
        self,
    ) -> Credentials:
        """
        Get valid Google OAuth credentials.
        Returns:
            Google OAuth credentials
        Raises:
            ValueError: If credentials have not been set
            Exception: If credential refresh fails
        """
        if not all(
            [
                self._credentials.client_id,
                self._credentials.client_secret,
                self._credentials.refresh_token,
            ]
        ):
            raise ValueError(
                "Google OAuth credentials (client_id, client_secret, refresh_token) must be set"
            )

        if self._credentials and not self._credentials.expired:
            return self._credentials

        # Create credentials from refresh token
        self._credentials = Credentials(
            token=self._credentials.token,
            refresh_token=self._credentials.refresh_token,
            token_uri=self._credentials.token_uri,
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            scopes=self._credentials.scopes,
            expiry=self._credentials.expiry,
        )

        # Refresh the token if needed
        if self._credentials.expired or not self._credentials.valid:
            try:
                self._credentials.refresh(Request())
                # Update the connector config in DB
                if self._session:
                    # Use connector_id if available, otherwise fall back to user_id query
                    if self._connector_id:
                        result = await self._session.execute(
                            select(SearchSourceConnector).filter(
                                SearchSourceConnector.id == self._connector_id
                            )
                        )
                    else:
                        result = await self._session.execute(
                            select(SearchSourceConnector).filter(
                                SearchSourceConnector.user_id == self._user_id,
                                SearchSourceConnector.connector_type
                                == SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
                            )
                        )
                    connector = result.scalars().first()
                    if connector is None:
                        raise RuntimeError(
                            "GOOGLE_CALENDAR_CONNECTOR connector not found; cannot persist refreshed token."
                        )
                    connector.config = json.loads(self._credentials.to_json())
                    flag_modified(connector, "config")
                    await self._session.commit()
            except Exception as e:
                raise Exception(
                    f"Failed to refresh Google OAuth credentials: {e!s}"
                ) from e

        return self._credentials

    async def _get_service(self):
        """
        Get the Google Calendar service instance using Google OAuth credentials.
        Returns:
            Google Calendar service instance
        Raises:
            ValueError: If credentials have not been set
            Exception: If service creation fails
        """
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("calendar", "v3", credentials=credentials)
            return self.service
        except Exception as e:
            raise Exception(f"Failed to create Google Calendar service: {e!s}") from e

    async def get_calendars(self) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch list of user's calendars using Google OAuth credentials.
        Returns:
            Tuple containing (calendars list, error message or None)
        """
        try:
            service = await self._get_service()
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get("items", [])

            # Format calendar data
            formatted_calendars = []
            for calendar in calendars:
                formatted_calendars.append(
                    {
                        "id": calendar.get("id"),
                        "summary": calendar.get("summary"),
                        "description": calendar.get("description", ""),
                        "primary": calendar.get("primary", False),
                        "accessRole": calendar.get("accessRole"),
                        "timeZone": calendar.get("timeZone"),
                    }
                )

            return formatted_calendars, None

        except Exception as e:
            return [], f"Error fetching calendars: {e!s}"

    async def get_all_primary_calendar_events(
        self,
        start_date: str,
        end_date: str,
        max_results: int = 2500,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch events from the primary calendar using Google OAuth credentials.
        Args:
            max_results: Maximum number of events to fetch (default: 2500)
        Returns:
            Tuple containing (events list, error message or None)
        """
        try:
            service = await self._get_service()

            # Parse both dates
            dt_start = isoparse(start_date)
            dt_end = isoparse(end_date)

            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=pytz.UTC)
            else:
                dt_start = dt_start.astimezone(pytz.UTC)

            if dt_end.tzinfo is None:
                dt_end = dt_end.replace(tzinfo=pytz.UTC)
            else:
                dt_end = dt_end.astimezone(pytz.UTC)

            if dt_start >= dt_end:
                return [], (
                    f"start_date ({dt_start.isoformat()}) must be strictly before "
                    f"end_date ({dt_end.isoformat()})."
                )

            # RFC3339 with 'Z' for UTC
            time_min = dt_start.isoformat().replace("+00:00", "Z")
            time_max = dt_end.isoformat().replace("+00:00", "Z")

            # Fetch events
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                    timeMin=time_min,
                    timeMax=time_max,
                )
                .execute()
            )

            events = events_result.get("items", [])

            if not events:
                return [], "No events found in the specified date range."

            return events, None

        except Exception as e:
            return [], f"Error fetching events: {e!s}"

    def format_event_to_markdown(self, event: dict[str, Any]) -> str:
        """
        Format a Google Calendar event to markdown.
        Args:
            event: Event object from Google Calendar API
        Returns:
            Formatted markdown string
        """
        # Extract basic event information
        summary = event.get("summary", "No Title")
        description = event.get("description", "")
        location = event.get("location", "")
        calendar_id = event.get("calendarId", "")

        # Extract start and end times
        start = event.get("start", {})
        end = event.get("end", {})

        start_time = start.get("dateTime") or start.get("date", "")
        end_time = end.get("dateTime") or end.get("date", "")

        # Format times for display
        if start_time:
            try:
                if "T" in start_time:  # DateTime format
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
                else:  # Date format (all-day event)
                    start_formatted = start_time
            except Exception:
                start_formatted = start_time
        else:
            start_formatted = "Unknown"

        if end_time:
            try:
                if "T" in end_time:  # DateTime format
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    end_formatted = end_dt.strftime("%Y-%m-%d %H:%M")
                else:  # Date format (all-day event)
                    end_formatted = end_time
            except Exception:
                end_formatted = end_time
        else:
            end_formatted = "Unknown"

        # Extract attendees
        attendees = event.get("attendees", [])
        attendee_list = []
        for attendee in attendees:
            email = attendee.get("email", "")
            display_name = attendee.get("displayName", email)
            response_status = attendee.get("responseStatus", "")
            attendee_list.append(f"- {display_name} ({response_status})")

        # Build markdown content
        markdown_content = f"# {summary}\n\n"

        # Add event details
        markdown_content += f"**Start:** {start_formatted}\n"
        markdown_content += f"**End:** {end_formatted}\n"

        if location:
            markdown_content += f"**Location:** {location}\n"

        if calendar_id:
            markdown_content += f"**Calendar:** {calendar_id}\n"

        markdown_content += "\n"

        # Add description if available
        if description:
            markdown_content += f"## Description\n\n{description}\n\n"

        # Add attendees if available
        if attendee_list:
            markdown_content += "## Attendees\n\n"
            markdown_content += "\n".join(attendee_list)
            markdown_content += "\n\n"

        # Add event metadata
        markdown_content += "## Event Details\n\n"
        markdown_content += f"- **Event ID:** {event.get('id', 'Unknown')}\n"
        markdown_content += f"- **Created:** {event.get('created', 'Unknown')}\n"
        markdown_content += f"- **Updated:** {event.get('updated', 'Unknown')}\n"

        if event.get("recurringEventId"):
            markdown_content += (
                f"- **Recurring Event ID:** {event.get('recurringEventId')}\n"
            )

        return markdown_content
