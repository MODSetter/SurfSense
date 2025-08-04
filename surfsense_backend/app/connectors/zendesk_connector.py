import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class ZendeskConnector:
    def __init__(self, subdomain: str, email: str, api_token: str):
        if not subdomain or not email or not api_token:
            raise ValueError("Subdomain, email, and API token cannot be empty.")
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)

    async def get_tickets(self, start_date: str | None = None):
        tickets = []
        # httpx default timeout is 5 seconds, which might be too short for fetching all tickets.
        # Setting a longer timeout and supporting configuration is a good practice.
        timeout_config = httpx.Timeout(30.0, connect=60.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            params = {}
            if start_date:
                try:
                    # Zendesk API uses 'start_time' for filtering by updated_at
                    # Convert YYYY-MM-DD to Unix timestamp
                    start_timestamp = int(
                        datetime.strptime(start_date, "%Y-%m-%d").timestamp()
                    )
                    params["start_time"] = start_timestamp
                except ValueError:
                    logger.error(
                        f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD."
                    )
                    return []

            url = f"{self.base_url}/tickets.json"
            while url:
                try:
                    response = await client.get(url, auth=self.auth, params=params)
                    response.raise_for_status()
                    data = response.json()
                    tickets.extend(data["tickets"])
                    url = data["next_page"]
                    # Clear params for subsequent paginated requests as they are part of the next_page URL
                    params = {}
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
                    )
                    break
                except httpx.RequestError as e:
                    logger.error(
                        f"An error occurred while requesting {e.request.url}: {e}"
                    )
                    break
        return tickets
