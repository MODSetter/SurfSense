import logging
import requests
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class TrelloConnector:
    """Connector for interacting with the Trello API."""

    BASE_URL = "https://api.trello.com/1"

    def __init__(self, api_key: str, token: str):
        """
        Initializes the Trello connector.

        Args:
            api_key: Trello API key.
            token: Trello API token.
        """
        if not api_key or not token:
            raise ValueError("Trello API key and token cannot be empty.")
        
        self.api_key = api_key
        self.token = token
        self.auth_params = {"key": self.api_key, "token": self.token}
        logger.info("Trello connector initialized.")

    def get_user_boards(self) -> List[Dict[str, Any]]:
        """Fetches all boards accessible by the user."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/members/me/boards", params=self.auth_params
            )
            response.raise_for_status()
            return [{"id": board["id"], "name": board["name"]} for board in response.json()]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Trello boards: {e}")
            return []

    def get_board_data(self, board_id: str) -> List[Dict[str, Any]]:
        """Fetches all cards for a given board."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/boards/{board_id}/cards", params=self.auth_params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch cards for board {board_id}: {e}")
            return []

    def get_card_details(self, card_id: str) -> Dict[str, Any]:
        """Fetches details for a specific card, including comments."""
        try:
            # Fetch card details
            card_response = requests.get(
                f"{self.BASE_URL}/cards/{card_id}", params=self.auth_params
            )
            card_response.raise_for_status()
            card_data = card_response.json()

            # Fetch card comments
            comments_response = requests.get(
                f"{self.BASE_URL}/cards/{card_id}/actions",
                params={**self.auth_params, "filter": "commentCard"},
            )
            comments_response.raise_for_status()
            comments_data = comments_response.json()

            card_data["comments"] = [
                comment["data"]["text"] for comment in comments_data
            ]
            return card_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch details for card {card_id}: {e}")
            return {}
