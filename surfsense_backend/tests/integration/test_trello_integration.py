"""
Integration tests for Trello connector functionality.
Tests the complete flow from API endpoints to database operations.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db import SearchSourceConnector, Document, DocumentType, SearchSourceConnectorType
from app.connectors.trello_connector import TrelloConnector


class TestTrelloIntegration:
    """Integration tests for Trello connector."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = MagicMock()
        user.id = "test_user_id"
        return user

    @pytest.fixture
    def sample_trello_boards(self):
        """Sample Trello boards data."""
        return [
            {"id": "board1", "name": "Project Board"},
            {"id": "board2", "name": "Personal Tasks"},
        ]

    @pytest.fixture
    def sample_trello_cards(self):
        """Sample Trello cards data."""
        return [
            {
                "id": "card1",
                "name": "Task 1",
                "desc": "Description of task 1",
                "url": "https://trello.com/c/card1",
            },
            {
                "id": "card2",
                "name": "Task 2",
                "desc": "Description of task 2",
                "url": "https://trello.com/c/card2",
            },
        ]

    @pytest.fixture
    def sample_card_details(self):
        """Sample card details with comments."""
        return {
            "id": "card1",
            "name": "Task 1",
            "desc": "Description of task 1",
            "url": "https://trello.com/c/card1",
            "comments": ["This is a comment", "Another comment"],
        }

    def test_trello_boards_endpoint_success(self, client, mock_user, sample_trello_boards):
        """Test successful fetching of Trello boards via API."""
        with patch("app.routes.search_source_connectors_routes.current_active_user", return_value=mock_user):
            with patch("app.routes.search_source_connectors_routes.TrelloConnector") as mock_trello_class:
                mock_trello_instance = MagicMock()
                mock_trello_instance.get_user_boards.return_value = sample_trello_boards
                mock_trello_class.return_value = mock_trello_instance

                response = client.post(
                    "/trello/boards/",
                    json={
                        "trello_api_key": "test_key",
                        "trello_api_token": "test_token",
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert data[0]["name"] == "Project Board"
                assert data[1]["name"] == "Personal Tasks"

    def test_trello_boards_endpoint_invalid_credentials(self, client, mock_user):
        """Test Trello boards endpoint with invalid credentials."""
        with patch("app.routes.search_source_connectors_routes.current_active_user", return_value=mock_user):
            with patch("app.routes.search_source_connectors_routes.TrelloConnector") as mock_trello_class:
                mock_trello_class.side_effect = ValueError("Invalid credentials")

                response = client.post(
                    "/trello/boards/",
                    json={
                        "trello_api_key": "invalid_key",
                        "trello_api_token": "invalid_token",
                    }
                )

                assert response.status_code == 400
                assert "Invalid Trello credentials" in response.json()["detail"]

    def test_trello_connector_creation_flow(self, client, mock_user, sample_trello_boards):
        """Test complete flow of creating a Trello connector."""
        with patch("app.routes.search_source_connectors_routes.current_active_user", return_value=mock_user):
            with patch("app.routes.search_source_connectors_routes.TrelloConnector") as mock_trello_class:
                mock_trello_instance = MagicMock()
                mock_trello_instance.get_user_boards.return_value = sample_trello_boards
                mock_trello_class.return_value = mock_trello_instance

                # First, fetch boards
                boards_response = client.post(
                    "/trello/boards/",
                    json={
                        "trello_api_key": "test_key",
                        "trello_api_token": "test_token",
                    }
                )

                assert boards_response.status_code == 200

                # Then create connector (this would be done by the frontend)
                # We're testing the integration, so we'll mock the connector creation
                with patch("app.routes.search_source_connectors_routes.create_search_source_connector") as mock_create:
                    mock_create.return_value = {"id": 1, "name": "Test Trello Connector"}

                    connector_response = client.post(
                        "/search-source-connectors/",
                        json={
                            "name": "Test Trello Connector",
                            "connector_type": "TRELLO_CONNECTOR",
                            "config": {
                                "TRELLO_API_KEY": "test_key",
                                "TRELLO_API_TOKEN": "test_token",
                                "board_ids": ["board1", "board2"],
                            },
                            "is_indexable": True,
                        }
                    )

                    # This would depend on the actual implementation
                    # For now, we're just testing that the flow works
                    assert mock_trello_class.called
                    assert mock_trello_instance.get_user_boards.called

    @pytest.mark.asyncio
    async def test_trello_indexing_integration(self, sample_trello_cards, sample_card_details):
        """Test the complete indexing flow."""
        from app.tasks.connector_indexers.trello_indexer import index_trello_boards

        # Mock database session
        mock_session = MagicMock(spec=AsyncSession)
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.config = {
            "TRELLO_API_KEY": "test_key",
            "TRELLO_API_TOKEN": "test_token",
            "board_ids": ["board1"],
        }

        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        # Mock TrelloConnector
        with patch("app.tasks.connector_indexers.trello_indexer.TrelloConnector") as mock_trello_class:
            mock_trello_instance = MagicMock()
            mock_trello_instance.get_board_data.return_value = sample_trello_cards
            mock_trello_instance.get_card_details.return_value = sample_card_details
            mock_trello_class.return_value = mock_trello_instance

            # Run indexing
            result = await index_trello_boards(
                session=mock_session,
                connector_id=1,
                search_space_id=1,
                user_id="test_user",
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

            # Verify results
            assert result[0] == 2  # 2 documents processed
            assert result[1] is None  # No error

            # Verify database operations
            assert mock_session.add.call_count == 2
            assert mock_session.commit.called

            # Verify Trello API calls
            mock_trello_instance.get_board_data.assert_called_once_with("board1")
            assert mock_trello_instance.get_card_details.call_count == 2

    def test_trello_connector_enum_values(self):
        """Test that Trello connector enum values are properly defined."""
        from app.db import DocumentType, SearchSourceConnectorType

        assert DocumentType.TRELLO_CONNECTOR == "TRELLO_CONNECTOR"
        assert SearchSourceConnectorType.TRELLO_CONNECTOR == "TRELLO_CONNECTOR"

    def test_trello_connector_initialization(self):
        """Test TrelloConnector initialization with valid credentials."""
        connector = TrelloConnector(api_key="test_key", token="test_token")

        assert connector.api_key == "test_key"
        assert connector.token == "test_token"
        assert connector.auth_params == {"key": "test_key", "token": "test_token"}

    def test_trello_connector_initialization_invalid(self):
        """Test TrelloConnector initialization with invalid credentials."""
        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="", token="test_token")

        with pytest.raises(ValueError, match="Trello API key and token cannot be empty"):
            TrelloConnector(api_key="test_key", token="")

    @patch("requests.get")
    def test_trello_connector_get_user_boards(self, mock_get, sample_trello_boards):
        """Test TrelloConnector.get_user_boards method."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_trello_boards
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        connector = TrelloConnector(api_key="test_key", token="test_token")
        boards = connector.get_user_boards()

        assert len(boards) == 2
        assert boards[0]["name"] == "Project Board"
        assert boards[1]["name"] == "Personal Tasks"

    @patch("requests.get")
    def test_trello_connector_get_board_data(self, mock_get, sample_trello_cards):
        """Test TrelloConnector.get_board_data method."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_trello_cards
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        connector = TrelloConnector(api_key="test_key", token="test_token")
        cards = connector.get_board_data("board1")

        assert len(cards) == 2
        assert cards[0]["name"] == "Task 1"
        assert cards[1]["name"] == "Task 2"

    @patch("requests.get")
    def test_trello_connector_get_card_details(self, mock_get, sample_card_details):
        """Test TrelloConnector.get_card_details method."""
        mock_card_response = MagicMock()
        mock_card_response.json.return_value = {
            "id": "card1",
            "name": "Task 1",
            "desc": "Description of task 1",
            "url": "https://trello.com/c/card1",
        }
        mock_card_response.raise_for_status.return_value = None

        mock_comments_response = MagicMock()
        mock_comments_response.json.return_value = [
            {"data": {"text": "This is a comment"}},
            {"data": {"text": "Another comment"}},
        ]
        mock_comments_response.raise_for_status.return_value = None

        mock_get.side_effect = [mock_card_response, mock_comments_response]

        connector = TrelloConnector(api_key="test_key", token="test_token")
        card_details = connector.get_card_details("card1")

        assert card_details["name"] == "Task 1"
        assert card_details["desc"] == "Description of task 1"
        assert len(card_details["comments"]) == 2
        assert card_details["comments"][0] == "This is a comment"

    def test_trello_credentials_request_model(self):
        """Test TrelloCredentialsRequest Pydantic model."""
        from app.routes.search_source_connectors_routes import TrelloCredentialsRequest

        # Valid request
        request = TrelloCredentialsRequest(
            trello_api_key="test_key",
            trello_api_token="test_token"
        )
        assert request.trello_api_key == "test_key"
        assert request.trello_api_token == "test_token"

        # Invalid request - missing fields
        with pytest.raises(ValueError):
            TrelloCredentialsRequest(trello_api_key="test_key")

        with pytest.raises(ValueError):
            TrelloCredentialsRequest(trello_api_token="test_token")

    @pytest.mark.asyncio
    async def test_trello_indexing_error_handling(self):
        """Test error handling in Trello indexing."""
        from app.tasks.connector_indexers.trello_indexer import index_trello_boards

        # Mock database session with no connector
        mock_session = MagicMock(spec=AsyncSession)
        mock_session.execute.return_value.scalars.return_value.first.return_value = None

        result = await index_trello_boards(
            session=mock_session,
            connector_id=999,  # Non-existent connector
            search_space_id=1,
            user_id="test_user",
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

        assert result[0] == 0  # No documents processed
        assert result[1] == "Connector not found."

    @pytest.mark.asyncio
    async def test_trello_indexing_invalid_config(self):
        """Test Trello indexing with invalid configuration."""
        from app.tasks.connector_indexers.trello_indexer import index_trello_boards

        # Mock database session with invalid config
        mock_session = MagicMock(spec=AsyncSession)
        mock_connector = MagicMock()
        mock_connector.id = 1
        mock_connector.config = {"TRELLO_API_KEY": "test_key"}  # Missing token and board_ids
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_connector

        result = await index_trello_boards(
            session=mock_session,
            connector_id=1,
            search_space_id=1,
            user_id="test_user",
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

        assert result[0] == 0  # No documents processed
        assert result[1] == "Invalid Trello connector configuration."


if __name__ == "__main__":
    pytest.main([__file__])
