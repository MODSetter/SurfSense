"""
Luma Connector Module

A module for retrieving events and guest data from Luma Event Platform.
Allows fetching event lists, event details, and guest information with date range filtering.
"""

from datetime import datetime
from typing import Any

import requests


class LumaConnector:
    """Class for retrieving events and guest data from Luma Event Platform."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize the LumaConnector class.

        Args:
            api_key: Luma API key (optional, can be set later with set_api_key)
        """
        self.api_key = api_key
        self.base_url = "https://public-api.luma.com/v1"

    def set_api_key(self, api_key: str) -> None:
        """
        Set the Luma API key.

        Args:
            api_key: Luma API key
        """
        self.api_key = api_key

    def get_headers(self) -> dict[str, str]:
        """
        Get headers for Luma API requests.

        Returns:
            Dictionary of headers

        Raises:
            ValueError: If no Luma API key has been set
        """
        if not self.api_key:
            raise ValueError("Luma API key not initialized. Call set_api_key() first.")

        return {
            "Content-Type": "application/json",
            "x-luma-api-key": self.api_key,
        }

    def make_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a request to the Luma API.

        Args:
            endpoint: API endpoint path (without base URL)
            params: Query parameters (optional)

        Returns:
            Response data from the API

        Raises:
            ValueError: If no Luma API key has been set
            Exception: If the API request fails
        """
        if not self.api_key:
            raise ValueError("Luma API key not initialized. Call set_api_key() first.")

        headers = self.get_headers()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise Exception("Unauthorized: Invalid Luma API key")
            elif response.status_code == 403:
                raise Exception(
                    "Forbidden: Access denied or Luma Plus subscription required"
                )
            elif response.status_code == 429:
                raise Exception("Rate limit exceeded: Too many requests")
            else:
                raise Exception(
                    f"API request failed with status code {response.status_code}: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {e}") from e

    def get_user_info(self) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get information about the authenticated user.

        Returns:
            Tuple containing (user info dict, error message or None)
        """
        try:
            user_info = self.make_request("user/get-self")
            return user_info, None
        except Exception as e:
            return None, f"Error fetching user info: {e!s}"

    def get_all_events(
        self, limit: int = 100
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch all events for the authenticated user.

        Args:
            limit: Maximum number of events to fetch per request (default: 100)

        Returns:
            Tuple containing (events list, error message or None)
        """
        try:
            all_events = []
            cursor = None

            while True:
                params = {"limit": limit}
                if cursor:
                    params["cursor"] = cursor

                response = self.make_request("calendar/list-events", params)

                if "entries" not in response:
                    break

                events = response["entries"]
                all_events.extend(events)

                # Check for pagination
                if response.get("next_cursor"):
                    cursor = response["next_cursor"]
                else:
                    break

            return all_events, None

        except Exception as e:
            return [], f"Error fetching events: {e!s}"

    def get_event_details(
        self, event_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Fetch detailed information about a specific event.

        Args:
            event_id: The ID of the event to fetch details for

        Returns:
            Tuple containing (event details dict, error message or None)
        """
        try:
            event_details = self.make_request(f"events/{event_id}")
            return event_details, None
        except Exception as e:
            return None, f"Error fetching event details for {event_id}: {e!s}"

    def get_event_guests(
        self, event_id: str, limit: int = 100
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch guests for a specific event.

        Args:
            event_id: The ID of the event to fetch guests for
            limit: Maximum number of guests to fetch per request (default: 100)

        Returns:
            Tuple containing (guests list, error message or None)
        """
        try:
            all_guests = []
            cursor = None

            while True:
                params = {"limit": limit}
                if cursor:
                    params["cursor"] = cursor

                response = self.make_request(f"events/{event_id}/guests", params)

                if "entries" not in response:
                    break

                guests = response["entries"]
                all_guests.extend(guests)

                # Check for pagination
                if response.get("next_cursor"):
                    cursor = response["next_cursor"]
                else:
                    break

            return all_guests, None

        except Exception as e:
            return [], f"Error fetching guests for event {event_id}: {e!s}"

    def get_events_by_date_range(
        self, start_date: str, end_date: str, include_guests: bool = True
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch events within a date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)
            include_guests: Whether to include guest information for each event

        Returns:
            Tuple containing (events list, error message or None)
        """
        try:
            # Convert date strings to ISO format for comparison
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # Get all events first
            all_events, error = self.get_all_events()
            if error:
                return [], error

            # Filter events by date range
            filtered_events = []
            for event in all_events:
                event_start_time = event.get("event", {}).get("start_at")
                if event_start_time:
                    try:
                        # Parse the event start time (assuming ISO format)
                        event_dt = datetime.fromisoformat(
                            event_start_time.replace("Z", "+00:00")
                        )
                        event_date = event_dt.date()

                        # Check if event falls within the date range
                        if start_dt.date() <= event_date <= end_dt.date():
                            # Add guest information if requested
                            if include_guests:
                                event_id = event.get("api_id")
                                if event_id:
                                    guests, guest_error = self.get_event_guests(
                                        event_id
                                    )
                                    if not guest_error:
                                        event["guests"] = guests

                            filtered_events.append(event)
                    except (ValueError, AttributeError):
                        # Skip events with invalid dates
                        continue

            if not filtered_events:
                return [], "No events found in the specified date range."

            return filtered_events, None

        except ValueError as e:
            return [], f"Invalid date format: {e!s}. Please use YYYY-MM-DD."
        except Exception as e:
            return [], f"Error fetching events by date range: {e!s}"

    def format_event_to_markdown(self, event: dict[str, Any]) -> str:
        """
        Convert an event to markdown format.

        Args:
            event: The event object from Luma API

        Returns:
            Markdown string representation of the event
        """
        # Extract event details
        event_data = event.get("event", {})

        title = event_data.get("name", "Untitled Event")
        description = event_data.get("description", "")
        event_id = event.get("api_id", "")

        # Extract timing information
        start_at = event_data.get("start_at", "")
        end_at = event_data.get("end_at", "")
        timezone = event_data.get("timezone", "")

        # Format dates
        start_formatted = self.format_date(start_at) if start_at else "Unknown"
        end_formatted = self.format_date(end_at) if end_at else "Unknown"

        # Extract location information
        geo_info = event_data.get("geo_info", {})
        location_name = geo_info.get("name", "")
        address = geo_info.get("address", "")

        # Extract other details
        url = event_data.get("url", "")
        visibility = event_data.get("visibility", "")
        meeting_url = event_data.get("meeting_url", "")

        # Build markdown content
        markdown_content = f"# {title}\n\n"

        if event_id:
            markdown_content += f"**Event ID:** {event_id}\n"

        # Add timing information
        markdown_content += f"**Start:** {start_formatted}\n"
        markdown_content += f"**End:** {end_formatted}\n"

        if timezone:
            markdown_content += f"**Timezone:** {timezone}\n"

        markdown_content += "\n"

        # Add location information
        if location_name or address:
            markdown_content += "## Location\n\n"
            if location_name:
                markdown_content += f"**Venue:** {location_name}\n"
            if address:
                markdown_content += f"**Address:** {address}\n"
            markdown_content += "\n"

        # Add online meeting info
        if meeting_url:
            markdown_content += f"**Meeting URL:** {meeting_url}\n\n"

        # Add description if available
        if description:
            markdown_content += f"## Description\n\n{description}\n\n"

        # Add event details
        markdown_content += "## Event Details\n\n"

        if url:
            markdown_content += f"- **Event URL:** {url}\n"

        if visibility:
            markdown_content += f"- **Visibility:** {visibility}\n"

        # Add guest information if available
        if "guests" in event:
            guests = event["guests"]
            markdown_content += f"\n## Guests ({len(guests)})\n\n"

            for guest in guests[:10]:  # Show first 10 guests
                guest_data = guest.get("guest", {})
                name = guest_data.get("name", "Unknown")
                email = guest_data.get("email", "")
                status = guest.get("registration_status", "unknown")

                markdown_content += f"- **{name}**"
                if email:
                    markdown_content += f" ({email})"
                markdown_content += f" - Status: {status}\n"

            if len(guests) > 10:
                markdown_content += f"- ... and {len(guests) - 10} more guests\n"

            markdown_content += "\n"

        return markdown_content

    @staticmethod
    def format_date(iso_date: str) -> str:
        """
        Format an ISO date string to a more readable format.

        Args:
            iso_date: ISO format date string

        Returns:
            Formatted date string
        """
        if not iso_date or not isinstance(iso_date, str):
            return "Unknown date"

        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            return iso_date


# Example usage (uncomment to use):
"""
if __name__ == "__main__":
    # Set your API key here
    api_key = "YOUR_LUMA_API_KEY"
    
    luma = LumaConnector(api_key)
    
    try:
        # Test authentication
        user_info, error = luma.get_user_info()
        if error:
            print(f"Authentication error: {error}")
        else:
            print(f"Authenticated as: {user_info.get('name', 'Unknown')}")
        
        # Get all events
        events, error = luma.get_all_events()
        if error:
            print(f"Error fetching events: {error}")
        else:
            print(f"Retrieved {len(events)} events")
            
            # Format and print the first event as markdown
            if events:
                event_md = luma.format_event_to_markdown(events[0])
                print("\nSample Event in Markdown:\n")
                print(event_md)
        
        # Get events by date range
        start_date = "2023-01-01"
        end_date = "2023-01-31"
        date_events, error = luma.get_events_by_date_range(start_date, end_date)
        
        if error:
            print(f"Error: {error}")
        else:
            print(f"\nRetrieved {len(date_events)} events from {start_date} to {end_date}")
    
    except Exception as e:
        print(f"Error: {e}")
"""
