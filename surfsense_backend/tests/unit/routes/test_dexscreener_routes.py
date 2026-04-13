"""Unit tests for DexScreener API routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.db import SearchSourceConnector, SearchSourceConnectorType, User, get_async_session
from app.users import current_active_user


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_connector():
    """Create a mock connector for testing."""
    connector = MagicMock(spec=SearchSourceConnector)
    connector.id = 1
    connector.name = "DexScreener Connector"
    connector.connector_type = SearchSourceConnectorType.DEXSCREENER_CONNECTOR
    connector.config = {
        "tokens": [
            {
                "chain": "ethereum",
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "name": "WETH",
            }
        ]
    }
    connector.search_space_id = 1
    connector.user_id = "test-user-id"
    connector.is_indexable = True
    return connector


@pytest.fixture
def client_with_overrides(mock_user, mock_session):
    """Create a test client with dependency overrides."""
    # Override dependencies
    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session
    
    client = TestClient(app)
    yield client
    
    # Clean up overrides after test
    app.dependency_overrides.clear()


class TestDexScreenerRoutes:
    """Test cases for DexScreener API routes."""

    @pytest.mark.asyncio
    async def test_add_connector_success_new(self, client_with_overrides, mock_session):
        """Test successful creation of a new connector."""
        request_data = {
            "tokens": [
                {
                    "chain": "ethereum",
                    "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    "name": "WETH",
                }
            ],
            "space_id": 1,
        }

        # Mock the database query to return no existing connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.post(
            "/api/v1/connectors/dexscreener/add", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "DexScreener connector added successfully"
        assert data["connector_type"] == "DEXSCREENER_CONNECTOR"
        assert data["tokens_count"] == 1
        assert "connector_id" in data

    @pytest.mark.asyncio
    async def test_add_connector_success_update_existing(
        self, client_with_overrides, mock_session, mock_connector
    ):
        """Test successful update of an existing connector."""
        request_data = {
            "tokens": [
                {
                    "chain": "ethereum",
                    "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    "name": "WETH",
                },
                {
                    "chain": "bsc",
                    "address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                    "name": "WBNB",
                },
            ],
            "space_id": 1,
        }

        # Mock the database query to return an existing connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_connector
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.post(
            "/api/v1/connectors/dexscreener/add", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "DexScreener connector updated successfully"
        assert data["connector_type"] == "DEXSCREENER_CONNECTOR"
        assert data["tokens_count"] == 2
        assert data["connector_id"] == 1

    def test_add_connector_invalid_tokens_missing_address(self, client_with_overrides):
        """Test connector addition with missing address field."""
        request_data = {
            "tokens": [{"chain": "ethereum"}],  # Missing address
            "space_id": 1,
        }

        response = client_with_overrides.post(
            "/api/v1/connectors/dexscreener/add", json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_add_connector_invalid_tokens_missing_chain(self, client_with_overrides):
        """Test connector addition with missing chain field."""
        request_data = {
            "tokens": [
                {"address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"}
            ],  # Missing chain
            "space_id": 1,
        }

        response = client_with_overrides.post(
            "/api/v1/connectors/dexscreener/add", json=request_data
        )

        assert response.status_code == 422  # Validation error

    def test_add_connector_empty_tokens_list(self, client_with_overrides):
        """Test connector addition with empty tokens list."""
        request_data = {
            "tokens": [],  # Empty list
            "space_id": 1,
        }

        response = client_with_overrides.post(
            "/api/v1/connectors/dexscreener/add", json=request_data
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_delete_connector_success(
        self, client_with_overrides, mock_session, mock_connector
    ):
        """Test successful connector deletion."""
        # Mock the database query to return an existing connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_connector
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.delete(
            "/api/v1/connectors/dexscreener",
            params={"space_id": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "DexScreener connector deleted successfully"
        mock_session.delete.assert_called_once_with(mock_connector)

    @pytest.mark.asyncio
    async def test_delete_connector_not_found(self, client_with_overrides, mock_session):
        """Test deletion of non-existent connector."""
        # Mock the database query to return no connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.delete(
            "/api/v1/connectors/dexscreener",
            params={"space_id": 999},
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_test_connector_success(
        self, client_with_overrides, mock_session, mock_connector, mock_pair_data
    ):
        """Test successful connector test."""
        # Mock the database query to return a connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_connector
        mock_session.execute.return_value = mock_result

        # Mock the DexScreenerConnector.get_token_pairs method
        with patch(
            "app.connectors.dexscreener_connector.DexScreenerConnector.get_token_pairs"
        ) as mock_get_pairs:
            # Return tuple (pairs, None) for success
            mock_get_pairs.return_value = (mock_pair_data["pairs"], None)

            response = client_with_overrides.get(
                "/api/v1/connectors/dexscreener/test", params={"space_id": 1}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "DexScreener connector is working correctly"
            assert data["tokens_configured"] == 1
            assert data["pairs_found"] == len(mock_pair_data["pairs"])
            assert "sample_pair" in data

    @pytest.mark.asyncio
    async def test_test_connector_not_found(self, client_with_overrides, mock_session):
        """Test connector test when connector doesn't exist."""
        # Mock the database query to return no connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.get(
            "/api/v1/connectors/dexscreener/test", params={"space_id": 999}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_test_connector_no_tokens(self, client_with_overrides, mock_session):
        """Test connector test with no tokens configured."""
        # Create a connector with empty tokens
        empty_connector = MagicMock(spec=SearchSourceConnector)
        empty_connector.config = {"tokens": []}

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = empty_connector
        mock_session.execute.return_value = mock_result

        response = client_with_overrides.get(
            "/api/v1/connectors/dexscreener/test", params={"space_id": 1}
        )

        assert response.status_code == 400
        data = response.json()
        assert "no tokens" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_test_connector_api_error(
        self, client_with_overrides, mock_session, mock_connector
    ):
        """Test connector test with API error."""
        # Mock the database query to return a connector
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_connector
        mock_session.execute.return_value = mock_result

        with patch(
            "app.connectors.dexscreener_connector.DexScreenerConnector.get_token_pairs"
        ) as mock_get_pairs:
            # Return tuple ([], error_message) for error
            mock_get_pairs.return_value = ([], "API Error: Connection failed")

            response = client_with_overrides.get(
                "/api/v1/connectors/dexscreener/test", params={"space_id": 1}
            )

            assert response.status_code == 400
            data = response.json()
            assert "failed to connect" in data["detail"].lower()
