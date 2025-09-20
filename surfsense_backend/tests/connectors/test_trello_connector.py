"""
Enhanced tests for TrelloConnector class.
Comprehensive test coverage for all Trello connector functionality.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock

from app.connectors.trello_connector import TrelloConnector


class TestTrelloConnector:
    """Test cases for TrelloConnector class."""

    @pytest.fixture
    def connector(self):
        """Create a TrelloConnector instance for testing."""
        return TrelloConnector(api_key="test_api_key", token="test_token")

    def test_initialization_success(self):
        """Test successful initialization of TrelloConnector."""
        connector = TrelloConnector(api_key="test_key", token="test_token")
        assert connector.api_key == "test_key"
        assert connector.token == "test_token"
        assert connector.auth_params == {"key": "test_key", "token": "test_token"}

    def test_initialization_empty_api_key(self):
        """Test initialization with empty API key."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="", token="test_token")

    def test_initialization_empty_token(self):
        """Test initialization with empty token."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="test_key", token="")

    def test_initialization_none_credentials(self):
        """Test initialization with None credentials."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key=None, token="test_token")
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="test_key", token=None)

    @patch("app.connectors.trello_connector.logger")
    def test_initialization_logs_success(self, mock_logger):
        """Test that initialization logs success message."""
        TrelloConnector(api_key="test_key", token="test_token")
        mock_logger.info.assert_called_with("Trello connector initialized.")

    @patch("requests.get")
    def test_get_user_boards_success(self, mock_get, connector):
        """Test successful fetching of user boards."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "board1", "name": "Board 1"},
            {"id": "board2", "name": "Board 2"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        boards = connector.get_user_boards()

        assert len(boards) == 2
        assert boards[0] == {"id": "board1", "name": "Board 1"}
        assert boards[1] == {"id": "board2", "name": "Board 2"}
        mock_get.assert_called_once_with(
            f"{connector.BASE_URL}/members/me/boards",
            params=connector.auth_params,
        )

    @patch("requests.get")
    def test_get_user_boards_failure(self, mock_get, connector):
        """Test failure in fetching user boards."""
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        boards = connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_user_boards_http_error(self, mock_get, connector):
        """Test HTTP error in fetching user boards."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_response

        boards = connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_board_data_success(self, mock_get, connector):
        """Test successful fetching of board data."""
        board_id = "board1"
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "card1", "name": "Card 1", "desc": "Description 1"},
            {"id": "card2", "name": "Card 2", "desc": "Description 2"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        cards = connector.get_board_data(board_id)

        assert len(cards) == 2
        assert cards[0]["name"] == "Card 1"
        assert cards[1]["name"] == "Card 2"
        mock_get.assert_called_once_with(
            f"{connector.BASE_URL}/boards/{board_id}/cards",
            params=connector.auth_params,
        )

    @patch("requests.get")
    def test_get_board_data_failure(self, mock_get, connector):
        """Test failure in fetching board data."""
        board_id = "board1"
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        cards = connector.get_board_data(board_id)

        assert len(cards) == 0

    @patch("requests.get")
    def test_get_card_details_success(self, mock_get, connector):
        """Test successful fetching of card details with comments."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1",
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = [
            {"data": {"text": "Comment 1"}},
            {"data": {"text": "Comment 2"}},
        ]
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert card_details["desc"] == "Description"
        assert card_details["url"] == "https://trello.com/c/card1"
        assert len(card_details["comments"]) == 2
        assert card_details["comments"][0] == "Comment 1"
        assert card_details["comments"][1] == "Comment 2"

        # Verify both API calls were made
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_get_card_details_failure(self, mock_get, connector):
        """Test failure in fetching card details."""
        card_id = "card1"
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        card_details = connector.get_card_details(card_id)

        assert card_details == {}

    @patch("requests.get")
    def test_get_card_details_no_comments(self, mock_get, connector):
        """Test fetching card details when there are no comments."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1",
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = []
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert card_details["comments"] == []

    @patch("requests.get")
    def test_get_card_details_card_fetch_failure(self, mock_get, connector):
        """Test failure in fetching card details when card fetch fails."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_card_response

        card_details = connector.get_card_details(card_id)

        assert card_details == {}

    @patch("requests.get")
    def test_get_card_details_comments_fetch_failure(self, mock_get, connector):
        """Test failure in fetching card details when comments fetch fails."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1",
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert card_details["desc"] == "Description"
        assert card_details["comments"] == []

    @patch("requests.get")
    def test_get_card_details_malformed_comments(self, mock_get, connector):
        """Test handling of malformed comments data."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1",
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = [
            {"data": {"text": "Valid comment"}},
            {"data": {}},  # Missing text field
            {"invalid": "structure"},  # Invalid structure
        ]
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert len(card_details["comments"]) == 1
        assert card_details["comments"][0] == "Valid comment"

    def test_base_url_constant(self, connector):
        """Test that BASE_URL constant is correctly set."""
        assert connector.BASE_URL == "https://api.trello.com/1"

    def test_auth_params_structure(self, connector):
        """Test that auth_params are correctly structured."""
        expected_params = {"key": "test_api_key", "token": "test_token"}
        assert connector.auth_params == expected_params

    @patch("requests.get")
    def test_get_user_boards_empty_response(self, mock_get, connector):
        """Test handling of empty response from get_user_boards."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        boards = connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_board_data_empty_response(self, mock_get, connector):
        """Test handling of empty response from get_board_data."""
        board_id = "board1"
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        cards = connector.get_board_data(board_id)

        assert len(cards) == 0

    @patch("requests.get")
    def test_get_user_boards_timeout(self, mock_get, connector):
        """Test timeout error in get_user_boards."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        boards = connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_board_data_timeout(self, mock_get, connector):
        """Test timeout error in get_board_data."""
        board_id = "board1"
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        cards = connector.get_board_data(board_id)

        assert len(cards) == 0

    @patch("requests.get")
    def test_get_card_details_timeout(self, mock_get, connector):
        """Test timeout error in get_card_details."""
        card_id = "card1"
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        card_details = connector.get_card_details(card_id)

        assert card_details == {}

    @patch("requests.get")
    def test_get_user_boards_connection_error(self, mock_get, connector):
        """Test connection error in get_user_boards."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        boards = connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_board_data_connection_error(self, mock_get, connector):
        """Test connection error in get_board_data."""
        board_id = "board1"
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        cards = connector.get_board_data(board_id)

        assert len(cards) == 0

    @patch("requests.get")
    def test_get_card_details_connection_error(self, mock_get, connector):
        """Test connection error in get_card_details."""
        card_id = "card1"
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        card_details = connector.get_card_details(card_id)

        assert card_details == {}


if __name__ == "__main__":
    pytest.main([__file__])
