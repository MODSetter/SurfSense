import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import BackgroundTasks, HTTPException

from app.main import app # Assuming your FastAPI app instance is here
from app.db import User, SearchSourceConnector, SearchSourceConnectorType, SearchSpace
from app.schemas.search_source_connector import SearchSourceConnectorRead # For response validation if needed
from app.connectors.slack_history import SlackHistory # To mock its methods
from slack_sdk.errors import SlackApiError

# --- Fixtures ---

@pytest.fixture
def mock_user():
    user = User(id="test_user_1", email="test@example.com", hashed_password="hashedpassword", is_active=True, is_superuser=False)
    return user

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock() # For individual record fetching by ID
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def mock_background_tasks():
    tasks = MagicMock(spec=BackgroundTasks)
    tasks.add_task = MagicMock()
    return tasks

@pytest.fixture
def test_client(mock_user, mock_db_session, mock_background_tasks):
    # Override dependencies
    app.dependency_overrides[current_active_user_dep] = lambda: mock_user
    app.dependency_overrides[get_async_session_dep] = lambda: mock_db_session
    # To inject BackgroundTasks, it's usually passed directly to the route function.
    # So, we'll mock it where it's used, or ensure it's injectable.
    # For testing, the TestClient can handle BackgroundTasks if routes are defined correctly.
    # If BackgroundTasks is a dependency, it can be overridden too.
    # For this test, we'll often patch where BackgroundTasks.add_task is called.
    return TestClient(app)

# --- Helper to get current_active_user dependency ---
# This is needed because current_active_user is likely defined in app.users
# and we need to provide the correct path for overriding.
# Assuming it's from app.users:
from app.users import current_active_user as current_active_user_dep
from app.db import get_async_session as get_async_session_dep


# --- Base Slack Connector Data ---
@pytest.fixture
def base_slack_connector_db():
    return SearchSourceConnector(
        id=1,
        user_id="test_user_1",
        name="Test Slack",
        connector_type=SearchSourceConnectorType.SLACK_CONNECTOR,
        is_indexable=True,
        config={"SLACK_BOT_TOKEN": "xoxb-valid-token"},
        last_indexed_at=None
    )

@pytest.fixture
def mock_search_space_db():
    return SearchSpace(id=1, name="Test Space", user_id="test_user_1")


# --- Test Classes ---

class TestDiscoverSlackChannels:

    @patch('app.routes.search_source_connectors_routes.SlackHistory')
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_success(self, mock_check_ownership, MockSlackHistory, test_client, mock_db_session, base_slack_connector_db):
        mock_check_ownership.return_value = base_slack_connector_db
        mock_db_session.get.return_value = base_slack_connector_db # For direct session.get calls

        mock_slack_instance = MockSlackHistory.return_value
        mock_slack_instance.get_all_channels.return_value = [
            {"id": "C1", "name": "General", "is_private": False, "is_member": True},
            {"id": "C2", "name": "Private", "is_private": True, "is_member": True},
            {"id": "C3", "name": "Public-NotMember", "is_private": False, "is_member": False},
        ]

        response = test_client.get("/api/v1/slack/1/discover-channels")

        assert response.status_code == 200
        data = response.json()
        assert len(data["channels"]) == 2 # C3 should be filtered out
        assert data["channels"][0]["id"] == "C1"
        assert data["channels"][1]["id"] == "C2"
        MockSlackHistory.assert_called_once_with(token="xoxb-valid-token")
        mock_slack_instance.get_all_channels.assert_called_once_with(include_private=True)

    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_connector_not_found(self, mock_check_ownership, test_client):
        mock_check_ownership.side_effect = HTTPException(status_code=404, detail="Connector not found")
        # Or, if session.get is used directly before check_ownership in the route:
        # mock_db_session.get.return_value = None
        # For this test, assuming check_ownership is the primary guard or session.get is part of it.

        response = test_client.get("/api/v1/slack/999/discover-channels")
        assert response.status_code == 404

    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_not_slack_connector(self, mock_check_ownership, test_client, base_slack_connector_db):
        base_slack_connector_db.connector_type = SearchSourceConnectorType.NOTION_CONNECTOR
        mock_check_ownership.return_value = base_slack_connector_db
        # mock_db_session.get.return_value = base_slack_connector_db

        response = test_client.get("/api/v1/slack/1/discover-channels")
        assert response.status_code == 400
        assert "Connector is not a Slack connector" in response.json()["detail"]

    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_token_not_configured(self, mock_check_ownership, test_client, base_slack_connector_db):
        base_slack_connector_db.config = {} # No token
        mock_check_ownership.return_value = base_slack_connector_db
        # mock_db_session.get.return_value = base_slack_connector_db

        response = test_client.get("/api/v1/slack/1/discover-channels")
        assert response.status_code == 400
        assert "Slack token not configured" in response.json()["detail"]

    @patch('app.routes.search_source_connectors_routes.SlackHistory')
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_slack_api_error(self, mock_check_ownership, MockSlackHistory, test_client, base_slack_connector_db):
        mock_check_ownership.return_value = base_slack_connector_db
        # mock_db_session.get.return_value = base_slack_connector_db
        
        mock_slack_instance = MockSlackHistory.return_value
        # Simulate SlackApiError with a mock response object that has a 'data' attribute
        mock_error_response = MagicMock()
        mock_error_response.data = {"error": "test_slack_api_error"}
        mock_slack_instance.get_all_channels.side_effect = SlackApiError("Slack API failed", mock_error_response)

        response = test_client.get("/api/v1/slack/1/discover-channels")
        assert response.status_code == 500 # Based on current route error handling
        assert "Slack API error: test_slack_api_error" in response.json()["detail"]

    @patch('app.routes.search_source_connectors_routes.SlackHistory')
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_discover_channels_value_error(self, mock_check_ownership, MockSlackHistory, test_client, base_slack_connector_db):
        mock_check_ownership.return_value = base_slack_connector_db
        # mock_db_session.get.return_value = base_slack_connector_db
        MockSlackHistory.side_effect = ValueError("Invalid token format") # Error on SlackHistory init

        response = test_client.get("/api/v1/slack/1/discover-channels")
        assert response.status_code == 400
        assert "Invalid token format" in response.json()["detail"]


class TestReindexSlackChannels:

    @patch('app.routes.search_source_connectors_routes.run_slack_indexing_with_new_session', new_callable=AsyncMock)
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_reindex_channels_success_defaults(self, mock_check_ownership, mock_run_indexing, test_client, mock_db_session, base_slack_connector_db, mock_search_space_db, mock_background_tasks):
        mock_check_ownership.return_value = base_slack_connector_db
        mock_db_session.get.return_value = base_slack_connector_db
        # Mock the search space query within the endpoint
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_search_space_db
        
        # Override BackgroundTasks for this specific test or ensure it's injected globally
        with patch('fastapi.BackgroundTasks', return_value=mock_background_tasks) as MockedBGTasks:
             # Re-apply dependency override if TestClient re-initializes app without it for BG tasks
            app.dependency_overrides[BackgroundTasks] = lambda: mock_background_tasks

            response = test_client.post("/api/v1/slack/1/reindex-channels", json={"channel_ids": ["C1", "C2"]})

            assert response.status_code == 202
            assert response.json()["message"] == "Re-indexing task for specific channels has been scheduled."
            
            mock_background_tasks.add_task.assert_called_once_with(
                mock_run_indexing, # Direct reference to the mocked task runner
                connector_id=1,
                search_space_id=mock_search_space_db.id,
                target_channel_ids=["C1", "C2"],
                force_reindex_all_messages=False, # Default
                reindex_start_date_str=None,      # Default
                reindex_latest_date_str=None       # Default
            )
            # Clean up dependency override if it was local to this test
            if BackgroundTasks in app.dependency_overrides:
                 del app.dependency_overrides[BackgroundTasks]


    @patch('app.routes.search_source_connectors_routes.run_slack_indexing_with_new_session', new_callable=AsyncMock)
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_reindex_channels_success_with_optional_params(self, mock_check_ownership, mock_run_indexing, test_client, mock_db_session, base_slack_connector_db, mock_search_space_db, mock_background_tasks):
        mock_check_ownership.return_value = base_slack_connector_db
        mock_db_session.get.return_value = base_slack_connector_db
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_search_space_db

        with patch('fastapi.BackgroundTasks', return_value=mock_background_tasks):
            app.dependency_overrides[BackgroundTasks] = lambda: mock_background_tasks
            payload = {
                "channel_ids": ["C1"],
                "force_reindex_all_messages": True,
                "reindex_start_date": "2023-01-01",
                "reindex_latest_date": "2023-01-31"
            }
            response = test_client.post("/api/v1/slack/1/reindex-channels", json=payload)

            assert response.status_code == 202
            mock_background_tasks.add_task.assert_called_once_with(
                mock_run_indexing,
                connector_id=1,
                search_space_id=mock_search_space_db.id,
                target_channel_ids=["C1"],
                force_reindex_all_messages=True,
                reindex_start_date_str="2023-01-01",
                reindex_latest_date_str="2023-01-31"
            )
            if BackgroundTasks in app.dependency_overrides:
                 del app.dependency_overrides[BackgroundTasks]

    # Error cases for reindex-channels (similar structure to discover-channels errors)
    # Connector not found, not Slack, token missing, no channel_ids
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_reindex_channels_no_channel_ids(self, mock_check_ownership, test_client, mock_db_session, base_slack_connector_db):
        mock_check_ownership.return_value = base_slack_connector_db
        mock_db_session.get.return_value = base_slack_connector_db
        
        response = test_client.post("/api/v1/slack/1/reindex-channels", json={"channel_ids": []}) # Empty list
        assert response.status_code == 400 # Or 422 depending on Pydantic validation
        assert "No channel_ids provided" in response.json()["detail"]


class TestIndexConnectorContentSlack:

    @patch('app.routes.search_source_connectors_routes.run_slack_indexing_with_new_session', new_callable=AsyncMock)
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_index_slack_connector_default(self, mock_check_ownership, mock_run_indexing, test_client, mock_db_session, base_slack_connector_db, mock_search_space_db, mock_background_tasks):
        # Mock check_ownership for connector and search_space
        mock_check_ownership.side_effect = [base_slack_connector_db, mock_search_space_db]
        
        with patch('fastapi.BackgroundTasks', return_value=mock_background_tasks):
            app.dependency_overrides[BackgroundTasks] = lambda: mock_background_tasks
            response = test_client.post("/api/v1/search-source-connectors/1/index?search_space_id=1")

            assert response.status_code == 200 # The route itself returns 200, task is background
            assert "Slack indexing started" in response.json()["message"]
            
            mock_background_tasks.add_task.assert_called_once_with(
                mock_run_indexing,
                1, # connector_id
                1, # search_space_id
                target_channel_ids=None, # From default in run_slack_indexing_with_new_session
                force_reindex_all_messages=False, # Default for this endpoint
                reindex_start_date_str=None,
                reindex_latest_date_str=None
            )
            if BackgroundTasks in app.dependency_overrides:
                 del app.dependency_overrides[BackgroundTasks]

    @patch('app.routes.search_source_connectors_routes.run_slack_indexing_with_new_session', new_callable=AsyncMock)
    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_index_slack_connector_force_full_reindex(self, mock_check_ownership, mock_run_indexing, test_client, mock_db_session, base_slack_connector_db, mock_search_space_db, mock_background_tasks):
        mock_check_ownership.side_effect = [base_slack_connector_db, mock_search_space_db]

        with patch('fastapi.BackgroundTasks', return_value=mock_background_tasks):
            app.dependency_overrides[BackgroundTasks] = lambda: mock_background_tasks
            response = test_client.post("/api/v1/search-source-connectors/1/index?search_space_id=1&force_full_reindex=true")

            assert response.status_code == 200
            assert "Full re-index initiated" in response.json()["message"]
            
            mock_background_tasks.add_task.assert_called_once_with(
                mock_run_indexing,
                1, 
                1, 
                target_channel_ids=None,
                force_reindex_all_messages=True, # Key check for this test
                reindex_start_date_str=None,
                reindex_latest_date_str=None
            )
            if BackgroundTasks in app.dependency_overrides:
                 del app.dependency_overrides[BackgroundTasks]

    @patch('app.routes.search_source_connectors_routes.check_ownership', new_callable=AsyncMock)
    async def test_index_connector_not_supported_type(self, mock_check_ownership, test_client, base_slack_connector_db, mock_search_space_db):
        base_slack_connector_db.connector_type = "UNSUPPORTED_TYPE" # Simulate an unsupported type
        mock_check_ownership.side_effect = [base_slack_connector_db, mock_search_space_db]

        response = test_client.post("/api/v1/search-source-connectors/1/index?search_space_id=1")
        assert response.status_code == 400
        assert "Indexing not supported for connector type: UNSUPPORTED_TYPE" in response.json()["detail"]

# It's important to clear dependency_overrides after tests if they are not scoped to TestClient instance
# However, pytest fixtures usually handle setup/teardown per test.
# If overrides are global to 'app', they might need explicit cleanup in a teardown fixture if not using TestClient's context management fully.
# For TestClient(app), it usually handles this.
