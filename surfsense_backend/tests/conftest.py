"""
Shared test fixtures and configuration for SurfSense Backend tests.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_user() -> MagicMock:
    """Create a mock user object."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    return user


@pytest.fixture
def mock_search_space() -> MagicMock:
    """Create a mock search space object."""
    search_space = MagicMock()
    search_space.id = 1
    search_space.name = "Test Search Space"
    search_space.llm_configs = []
    search_space.fast_llm_id = None
    search_space.long_context_llm_id = None
    search_space.strategic_llm_id = None
    return search_space


@pytest.fixture
def sample_messages() -> list[dict]:
    """Sample chat messages for testing."""
    return [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"},
        {"role": "user", "content": "What is the weather today?"},
    ]


@pytest.fixture
def sample_chat_create_data() -> dict:
    """Sample data for creating a chat."""
    return {
        "title": "Test Chat",
        "type": "normal",
        "search_space_id": 1,
        "initial_connectors": [],
        "messages": [],
    }
