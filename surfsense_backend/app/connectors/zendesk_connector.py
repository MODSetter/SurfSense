from datetime import datetime

import httpx


class ZendeskConnector:
    def __init__(self, subdomain: str, email: str, api_token: str):
        if not subdomain or not email or not api_token:
            raise ValueError("Subdomain, email, and API token cannot be empty.")
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)

    async def get_tickets(
        self, start_date: str | None = None, end_date: str | None = None
    ):
        tickets = []
        async with httpx.AsyncClient() as client:
            params = {}
            if start_date:
                # Zendesk API uses 'start_time' for filtering by updated_at
                # Convert YYYY-MM-DD to Unix timestamp
                start_timestamp = int(
                    datetime.strptime(start_date, "%Y-%m-%d").timestamp()
                )
                params["start_time"] = start_timestamp

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
                    print(
                        f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
                    )
                    break
                except httpx.RequestError as e:
                    print(f"An error occurred while requesting {e.request.url}: {e}")
                    break
        return tickets
