"""
Comprehensive tests for Trello connector functionality.
Tests all aspects of the Trello connector implementation.
"""

import pytest
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.trello_connector import TrelloConnector
from app.tasks.connector_indexers.trello_indexer import index_trello_boards
from app.db import SearchSourceConnector, Document, DocumentType, SearchSourceConnectorType
from app.routes.search_source_connectors_routes import (
    TrelloCredentialsRequest,
    list_trello_boards,
    run_trello_indexing,
    run_trello_indexing_with_new_session,
)
from app.main import app


class TestTrelloConnector:
    """Test cases for TrelloConnector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.token = "test_token"
        self.connector = TrelloConnector(api_key=self.api_key, token=self.token)

    def test_initialization_success(self):
        """Test successful initialization of TrelloConnector."""
        connector = TrelloConnector(api_key=self.api_key, token=self.token)
        assert connector.api_key == self.api_key
        assert connector.token == self.token
        assert connector.auth_params == {"key": self.api_key, "token": self.token}

    def test_initialization_empty_api_key(self):
        """Test initialization with empty API key."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="", token=self.token)

    def test_initialization_empty_token(self):
        """Test initialization with empty token."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key=self.api_key, token="")

    def test_initialization_none_credentials(self):
        """Test initialization with None credentials."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key=None, token=self.token)
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key=self.api_key, token=None)

    @patch("requests.get")
    def test_get_user_boards_success(self, mock_get):
        """Test successful fetching of user boards."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "board1", "name": "Board 1"},
            {"id": "board2", "name": "Board 2"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        boards = self.connector.get_user_boards()

        assert len(boards) == 2
        assert boards[0] == {"id": "board1", "name": "Board 1"}
        assert boards[1] == {"id": "board2", "name": "Board 2"}
        mock_get.assert_called_once_with(
            f"{self.connector.BASE_URL}/members/me/boards",
            params=self.connector.auth_params,
        )

    @patch("requests.get")
    def test_get_user_boards_failure(self, mock_get):
        """Test failure in fetching user boards."""
        mock_get.side_effect = Exception("API error")

        boards = self.connector.get_user_boards()

        assert len(boards) == 0

    @patch("requests.get")
    def test_get_board_data_success(self, mock_get):
        """Test successful fetching of board data."""
        board_id = "board1"
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "card1", "name": "Card 1", "desc": "Description 1"},
            {"id": "card2", "name": "Card 2", "desc": "Description 2"},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        cards = self.connector.get_board_data(board_id)

        assert len(cards) == 2
        assert cards[0]["name"] == "Card 1"
        assert cards[1]["name"] == "Card 2"
        mock_get.assert_called_once_with(
            f"{self.connector.BASE_URL}/boards/{board_id}/cards",
            params=self.connector.auth_params,
        )

    @patch("requests.get")
    def test_get_board_data_failure(self, mock_get):
        """Test failure in fetching board data."""
        board_id = "board1"
        mock_get.side_effect = Exception("API error")

        cards = self.connector.get_board_data(board_id)

        assert len(cards) == 0

    @patch("requests.get")
    def test_get_card_details_success(self, mock_get):
        """Test successful fetching of card details with comments."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1"
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = [
            {"data": {"text": "Comment 1"}},
            {"data": {"text": "Comment 2"}},
        ]
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = self.connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert card_details["desc"] == "Description"
        assert card_details["url"] == "https://trello.com/c/card1"
        assert len(card_details["comments"]) == 2
        assert card_details["comments"][0] == "Comment 1"
        assert card_details["comments"][1] == "Comment 2"

        # Verify both API calls were made
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_get_card_details_failure(self, mock_get):
        """Test failure in fetching card details."""
        card_id = "card1"
        mock_get.side_effect = Exception("API error")

        card_details = self.connector.get_card_details(card_id)

        assert card_details == {}

    @patch("requests.get")
    def test_get_card_details_no_comments(self, mock_get):
        """Test fetching card details when there are no comments."""
        card_id = "card1"
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Card 1",
            "desc": "Description",
            "url": "https://trello.com/c/card1"
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = []
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        card_details = self.connector.get_card_details(card_id)

        assert card_details["name"] == "Card 1"
        assert card_details["comments"] == []


class TestTrelloIndexer:
    """Test cases for Trello indexer functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def mock_connector(self):
        """Create a mock connector."""
        connector = MagicMock()
        connector.id = 1
        connector.config = {
            "TRELLO_API_KEY": "test_api_key",
            "TRELLO_API_TOKEN": "test_token",
            "board_ids": ["board1", "board2"]
        }
        return connector

    @pytest.mark.asyncio
    async def test_index_trello_boards_connector_not_found(self, mock_session):
        """Test indexing when connector is not found."""
        mock_session.execute.return_value.scalars.return_value.first.return_value = None

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert result == (0, "Connector not found.")

    @pytest.mark.asyncio
    async def test_index_trello_boards_invalid_config(self, mock_session, mock_connector):
        """Test indexing with invalid connector configuration."""
        mock_connector.config = {"TRELLO_API_KEY": "test_key"}  # Missing token and board_ids
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert result == (0, "Invalid Trello connector configuration.")

    @pytest.mark.asyncio
    @patch("app.tasks.connector_indexers.trello_indexer.TrelloConnector")
    async def test_index_trello_boards_success(self, mock_trello_class, mock_session, mock_connector):
        """Test successful indexing of Trello boards."""
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        # Mock TrelloConnector instance
        mock_trello_instance = MagicMock()
        mock_trello_instance.get_board_data.side_effect = [
            [{"id": "card1", "name": "Card 1"}],
            [{"id": "card2", "name": "Card 2"}]
        ]
        mock_trello_instance.get_card_details.side_effect = [
            {
                "id": "card1",
                "name": "Card 1",
                "desc": "Description 1",
                "url": "https://trello.com/c/card1",
                "comments": ["Comment 1"]
            },
            {
                "id": "card2",
                "name": "Card 2",
                "desc": "Description 2",
                "url": "https://trello.com/c/card2",
                "comments": []
            }
        ]
        mock_trello_class.return_value = mock_trello_instance

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert result[0] == 2  # 2 documents processed
        assert result[1] is None  # No error
        assert mock_session.add.call_count == 2
        assert mock_session.commit.called

    @pytest.mark.asyncio
    @patch("app.tasks.connector_indexers.trello_indexer.TrelloConnector")
    async def test_index_trello_boards_no_cards(self, mock_trello_class, mock_session, mock_connector):
        """Test indexing when there are no cards."""
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        # Mock TrelloConnector instance with no cards
        mock_trello_instance = MagicMock()
        mock_trello_instance.get_board_data.return_value = []
        mock_trello_class.return_value = mock_trello_instance

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert result[0] == 0  # No documents processed
        assert result[1] is None  # No error
        assert not mock_session.add.called
        assert not mock_session.commit.called

    @pytest.mark.asyncio
    @patch("app.tasks.connector_indexers.trello_indexer.TrelloConnector")
    async def test_index_trello_boards_card_details_failure(self, mock_trello_class, mock_session, mock_connector):
        """Test indexing when card details cannot be fetched."""
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        # Mock TrelloConnector instance
        mock_trello_instance = MagicMock()
        mock_trello_instance.get_board_data.return_value = [{"id": "card1", "name": "Card 1"}]
        mock_trello_instance.get_card_details.return_value = {}  # Empty details
        mock_trello_class.return_value = mock_trello_instance

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert result[0] == 0  # No documents processed
        assert result[1] is None  # No error
        assert not mock_session.add.called
        assert not mock_session.commit.called


class TestTrelloRoutes:
    """Test cases for Trello API routes."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    @patch("app.routes.search_source_connectors_routes.TrelloConnector")
    def test_list_trello_boards_success(self, mock_trello_class):
        """Test successful listing of Trello boards."""
        # Mock TrelloConnector
        mock_trello_instance = MagicMock()
        mock_trello_instance.get_user_boards.return_value = [
            {"id": "board1", "name": "Board 1"},
            {"id": "board2", "name": "Board 2"}
        ]
        mock_trello_class.return_value = mock_trello_instance

        # Mock current_active_user dependency
        with patch("app.routes.search_source_connectors_routes.current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id="user1")

            response = self.client.post(
                "/trello/boards/",
                json={
                    "trello_api_key": "test_key",
                    "trello_api_token": "test_token"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "Board 1"
            assert data[1]["name"] == "Board 2"

    @patch("app.routes.search_source_connectors_routes.TrelloConnector")
    def test_list_trello_boards_invalid_credentials(self, mock_trello_class):
        """Test listing Trello boards with invalid credentials."""
        # Mock TrelloConnector to raise ValueError
        mock_trello_class.side_effect = ValueError("Invalid credentials")

        # Mock current_active_user dependency
        with patch("app.routes.search_source_connectors_routes.current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id="user1")

            response = self.client.post(
                "/trello/boards/",
                json={
                    "trello_api_key": "invalid_key",
                    "trello_api_token": "invalid_token"
                }
            )

            assert response.status_code == 400
            assert "Invalid Trello credentials" in response.json()["detail"]

    @patch("app.routes.search_source_connectors_routes.TrelloConnector")
    def test_list_trello_boards_api_error(self, mock_trello_class):
        """Test listing Trello boards with API error."""
        # Mock TrelloConnector
        mock_trello_instance = MagicMock()
        mock_trello_instance.get_user_boards.side_effect = Exception("API error")
        mock_trello_class.return_value = mock_trello_instance

        # Mock current_active_user dependency
        with patch("app.routes.search_source_connectors_routes.current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id="user1")

            response = self.client.post(
                "/trello/boards/",
                json={
                    "trello_api_key": "test_key",
                    "trello_api_token": "test_token"
                }
            )

            assert response.status_code == 500
            assert "Failed to fetch Trello boards" in response.json()["detail"]


class TestTrelloCredentialsRequest:
    """Test cases for TrelloCredentialsRequest model."""

    def test_valid_credentials(self):
        """Test valid credentials."""
        request = TrelloCredentialsRequest(
            trello_api_key="test_key",
            trello_api_token="test_token"
        )
        assert request.trello_api_key == "test_key"
        assert request.trello_api_token == "test_token"

    def test_missing_api_key(self):
        """Test missing API key."""
        with pytest.raises(ValueError):
            TrelloCredentialsRequest(trello_api_token="test_token")

    def test_missing_token(self):
        """Test missing token."""
        with pytest.raises(ValueError):
            TrelloCredentialsRequest(trello_api_key="test_key")


class TestTrelloIndexingFunctions:
    """Test cases for Trello indexing helper functions."""

    @pytest.mark.asyncio
    @patch("app.routes.search_source_connectors_routes.async_session_maker")
    @patch("app.routes.search_source_connectors_routes.run_trello_indexing")
    async def test_run_trello_indexing_with_new_session(self, mock_run_indexing, mock_session_maker):
        """Test running Trello indexing with new session."""
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session

        await run_trello_indexing_with_new_session(
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        mock_run_indexing.assert_called_once_with(
            mock_session, 1, 1, "user1", "2023-01-01", "2023-12-31"
        )

    @pytest.mark.asyncio
    @patch("app.routes.search_source_connectors_routes.index_trello_boards")
    @patch("app.routes.search_source_connectors_routes.update_connector_last_indexed")
    async def test_run_trello_indexing_success(self, mock_update_indexed, mock_index_boards):
        """Test successful Trello indexing."""
        mock_session = AsyncMock()
        mock_index_boards.return_value = (5, None)  # 5 documents, no error

        await run_trello_indexing(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        mock_index_boards.assert_called_once()
        mock_update_indexed.assert_called_once_with(mock_session, 1)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.routes.search_source_connectors_routes.index_trello_boards")
    async def test_run_trello_indexing_failure(self, mock_index_boards):
        """Test Trello indexing failure."""
        mock_session = AsyncMock()
        mock_index_boards.return_value = (0, "Indexing failed")

        await run_trello_indexing(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="user1",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        mock_index_boards.assert_called_once()
        mock_session.rollback.assert_called_once()


class TestTrelloDatabaseIntegration:
    """Test cases for Trello database integration."""

    def test_trello_connector_enum_values(self):
        """Test that TRELLO_CONNECTOR is properly defined in enums."""
        from app.db import DocumentType, SearchSourceConnectorType

        assert DocumentType.TRELLO_CONNECTOR == "TRELLO_CONNECTOR"
        assert SearchSourceConnectorType.TRELLO_CONNECTOR == "TRELLO_CONNECTOR"

    def test_trello_connector_enum_in_connector_ts(self):
        """Test that TRELLO_CONNECTOR is defined in frontend enum."""
        # This would need to be tested in the frontend test suite
        # For now, we'll just verify the enum exists
        from surfsense_web.contracts.enums.connector import EnumConnectorName
        
        assert hasattr(EnumConnectorName, 'TRELLO_CONNECTOR')
        assert EnumConnectorName.TRELLO_CONNECTOR == "TRELLO_CONNECTOR"


if __name__ == "__main__":
    pytest.main([__file__])
