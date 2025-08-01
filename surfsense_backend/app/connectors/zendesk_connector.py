import httpx


class ZendeskConnector:
    def __init__(self, subdomain: str, email: str, api_token: str):
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)

    async def get_tickets(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/tickets.json", auth=self.auth)
            response.raise_for_status()
            return response.json()["tickets"]
