"""
Pytest configuration and fixtures for Trello connector tests.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_async_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def sample_trello_boards():
    """Sample Trello boards data for testing."""
    return [
        {"id": "board1", "name": "Project Board"},
        {"id": "board2", "name": "Personal Tasks"},
        {"id": "board3", "name": "Team Collaboration"},
    ]


@pytest.fixture
def sample_trello_cards():
    """Sample Trello cards data for testing."""
    return [
        {
            "id": "card1",
            "name": "Implement user authentication",
            "desc": "Add login and registration functionality",
            "url": "https://trello.com/c/card1",
            "due": "2023-12-31T23:59:59.000Z",
            "labels": [{"name": "High Priority", "color": "red"}],
        },
        {
            "id": "card2",
            "name": "Design database schema",
            "desc": "Create ERD and define table relationships",
            "url": "https://trello.com/c/card2",
            "due": None,
            "labels": [{"name": "Design", "color": "blue"}],
        },
        {
            "id": "card3",
            "name": "Write API documentation",
            "desc": "Document all REST endpoints",
            "url": "https://trello.com/c/card3",
            "due": "2023-12-15T12:00:00.000Z",
            "labels": [{"name": "Documentation", "color": "green"}],
        },
    ]


@pytest.fixture
def sample_card_details():
    """Sample card details with comments for testing."""
    return {
        "id": "card1",
        "name": "Implement user authentication",
        "desc": "Add login and registration functionality with JWT tokens",
        "url": "https://trello.com/c/card1",
        "due": "2023-12-31T23:59:59.000Z",
        "labels": [{"name": "High Priority", "color": "red"}],
        "comments": [
            "This is a high priority task that needs to be completed by end of year",
            "Make sure to include password reset functionality",
            "Consider using OAuth2 for social login",
        ],
    }


@pytest.fixture
def sample_trello_connector_config():
    """Sample Trello connector configuration."""
    return {
        "TRELLO_API_KEY": "test_api_key_12345",
        "TRELLO_API_TOKEN": "test_token_67890",
        "board_ids": ["board1", "board2", "board3"],
    }


@pytest.fixture
def mock_trello_connector():
    """Mock TrelloConnector instance."""
    connector = MagicMock()
    connector.api_key = "test_api_key"
    connector.token = "test_token"
    connector.auth_params = {"key": "test_api_key", "token": "test_token"}
    return connector


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    user = MagicMock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_search_space():
    """Mock search space for testing."""
    search_space = MagicMock()
    search_space.id = 1
    search_space.name = "Test Search Space"
    search_space.user_id = "test_user_123"
    return search_space


@pytest.fixture
def mock_connector():
    """Mock SearchSourceConnector for testing."""
    connector = MagicMock()
    connector.id = 1
    connector.name = "Test Trello Connector"
    connector.connector_type = "TRELLO_CONNECTOR"
    connector.config = {
        "TRELLO_API_KEY": "test_api_key",
        "TRELLO_API_TOKEN": "test_token",
        "board_ids": ["board1", "board2"],
    }
    connector.is_indexable = True
    connector.user_id = "test_user_123"
    return connector


@pytest.fixture
def sample_document_metadata():
    """Sample document metadata for testing."""
    return {
        "board_id": "board1",
        "card_id": "card1",
        "url": "https://trello.com/c/card1",
        "due_date": "2023-12-31T23:59:59.000Z",
        "labels": [{"name": "High Priority", "color": "red"}],
        "comment_count": 3,
    }


@pytest.fixture
def sample_document_content():
    """Sample document content for testing."""
    return """Card: Implement user authentication

Description: Add login and registration functionality with JWT tokens

Comments:
- This is a high priority task that needs to be completed by end of year
- Make sure to include password reset functionality
- Consider using OAuth2 for social login
"""


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for testing API calls."""
    import requests
    from unittest.mock import patch

    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for testing API calls."""
    import requests
    from unittest.mock import patch

    with patch("requests.post") as mock_post:
        yield mock_post


@pytest.fixture
def mock_fetch():
    """Mock global fetch for frontend testing."""
    from unittest.mock import patch

    with patch("global.fetch") as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_toast():
    """Mock toast notifications for frontend testing."""
    from unittest.mock import patch

    with patch("sonner.toast") as mock_toast:
        yield mock_toast


@pytest.fixture
def mock_router():
    """Mock Next.js router for frontend testing."""
    from unittest.mock import patch

    with patch("next/navigation.useRouter") as mock_use_router:
        mock_router = MagicMock()
        mock_router.push = MagicMock()
        mock_router.back = MagicMock()
        mock_use_router.return_value = mock_router
        yield mock_router


@pytest.fixture
def mock_params():
    """Mock Next.js params for frontend testing."""
    from unittest.mock import patch

    with patch("next/navigation.useParams") as mock_use_params:
        mock_use_params.return_value = {"search_space_id": "1"}
        yield mock_use_params


@pytest.fixture
def mock_use_search_source_connectors():
    """Mock useSearchSourceConnectors hook for frontend testing."""
    from unittest.mock import patch

    with patch("hooks.useSearchSourceConnectors") as mock_hook:
        mock_hook.return_value = {
            "createConnector": MagicMock(),
            "updateConnector": MagicMock(),
            "deleteConnector": MagicMock(),
            "isLoading": False,
            "error": None,
        }
        yield mock_hook


# Test data for various scenarios
@pytest.fixture
def trello_api_responses():
    """Various Trello API response scenarios for testing."""
    return {
        "success_boards": [
            {"id": "board1", "name": "Project Board"},
            {"id": "board2", "name": "Personal Tasks"},
        ],
        "success_cards": [
            {
                "id": "card1",
                "name": "Task 1",
                "desc": "Description 1",
                "url": "https://trello.com/c/card1",
            }
        ],
        "success_card_details": {
            "id": "card1",
            "name": "Task 1",
            "desc": "Description 1",
            "url": "https://trello.com/c/card1",
            "comments": ["Comment 1", "Comment 2"],
        },
        "error_response": {
            "status_code": 401,
            "message": "Unauthorized",
        },
        "empty_response": [],
    }


@pytest.fixture
def trello_error_scenarios():
    """Various error scenarios for Trello connector testing."""
    return {
        "invalid_credentials": ValueError("Invalid Trello credentials"),
        "api_error": Exception("Trello API error"),
        "network_error": ConnectionError("Network connection failed"),
        "timeout_error": TimeoutError("Request timed out"),
        "rate_limit_error": Exception("Rate limit exceeded"),
    }
