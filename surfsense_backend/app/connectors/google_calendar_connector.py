"""
Google Calendar Connector

A module for interacting with Google Calendar API to retrieve calendar lists and event history.

Requires OAuth2 credentials.
"""

import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class GoogleCalendarConnector:
    """Class for retrieving calendar and event history from Google Calendar."""
    def __init__(self, credentials_dict: dict = None):
        """
        Initialize the GoogleCalendarConnector with OAuth2 credentials.
        Args:
            credentials_dict (dict): The OAuth2 credentials as a dict.
        """
        if credentials_dict:
            self.creds = Credentials.from_authorized_user_info(credentials_dict)
            self.service = build('calendar', 'v3', credentials=self.creds)
        else:
            self.creds = None
            self.service = None

    def set_credentials(self, credentials_dict: dict) -> None:
        """Set the OAuth2 credentials."""
        self.creds = Credentials.from_authorized_user_info(credentials_dict)
        self.service = build('calendar', 'v3', credentials=self.creds)

    def get_calendars(self) -> List[Dict]:
        """Fetch all calendars accessible by the user."""
        if not self.service:
            raise ValueError("Google Calendar service not initialized. Call set_credentials() first.")
        calendars = self.service.calendarList().list().execute()
        return calendars.get('items', [])

    def get_events(self, calendar_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Fetch events from a calendar within an optional date range (ISO format)."""
        if not self.service:
            raise ValueError("Google Calendar service not initialized. Call set_credentials() first.")
        time_min = start_date + 'T00:00:00Z' if start_date else None
        time_max = end_date + 'T23:59:59Z' if end_date else None
        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])

    def get_event_details(self, calendar_id: str, event_id: str) -> Dict:
        """Fetch details for a specific event."""
        if not self.service:
            raise ValueError("Google Calendar service not initialized. Call set_credentials() first.")
        event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return event 