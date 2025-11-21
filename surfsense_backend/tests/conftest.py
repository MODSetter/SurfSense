"""
Pytest configuration and shared fixtures for SurfSense backend tests.

This module provides:
- Database fixtures (test DB, session, async session)
- Authentication fixtures (test users, tokens)
- Application fixtures (test client, app instance)
- Mock fixtures (external services, connectors)
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from faker import Faker
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.app import app as fastapi_app
from app.db import Base, User

# Initialize Faker for generating test data
fake = Faker()


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get test database URL from environment or use in-memory SQLite."""
    # Use in-memory SQLite for testing by default
    return "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine(test_database_url: str):
    """Create async database engine for testing."""
    engine = create_async_engine(
        test_database_url,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False} if "sqlite" in test_database_url else {},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def test_client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with database session override."""
    from app.app import get_async_session

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    fastapi_app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test"
    ) as client:
        yield client

    # Clean up overrides
    fastapi_app.dependency_overrides.clear()


# ===========================
# User and Authentication Fixtures
# ===========================


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create a test user."""
    from app.users import get_user_manager

    user_data = {
        "email": fake.email(),
        "password": "TestPassword123!",
        "is_active": True,
        "is_superuser": False,
        "is_verified": True,
    }

    # Create user using the user manager
    user = User(
        email=user_data["email"],
        hashed_password="hashed_password_here",  # Will be hashed properly in real scenario
        is_active=user_data["is_active"],
        is_superuser=user_data["is_superuser"],
        is_verified=user_data["is_verified"],
    )

    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def test_superuser(async_session: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        email=fake.email(),
        hashed_password="hashed_password_here",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )

    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def test_user_with_2fa(async_session: AsyncSession) -> User:
    """Create a test user with 2FA enabled."""
    import pyotp

    totp_secret = pyotp.random_base32()

    user = User(
        email=fake.email(),
        hashed_password="hashed_password_here",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        two_fa_enabled=True,
        totp_secret=totp_secret,
    )

    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Generate JWT token for test user."""
    # This would use your actual JWT generation logic
    return "test_jwt_token_" + str(test_user.id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Generate authorization headers for requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ===========================
# Database Model Fixtures
# ===========================


@pytest_asyncio.fixture
async def test_search_space(async_session: AsyncSession, test_user: User):
    """Create a test search space."""
    from app.db import SearchSpace

    search_space = SearchSpace(
        name=fake.word(),
        description=fake.sentence(),
        user_id=test_user.id,
    )

    async_session.add(search_space)
    await async_session.commit()
    await async_session.refresh(search_space)

    return search_space


@pytest_asyncio.fixture
async def test_document(async_session: AsyncSession, test_search_space):
    """Create a test document."""
    from app.db import Document, DocumentType

    document = Document(
        title=fake.sentence(),
        content=fake.text(),
        source=fake.url(),
        search_space_id=test_search_space.id,
        document_type=DocumentType.WEB,
    )

    async_session.add(document)
    await async_session.commit()
    await async_session.refresh(document)

    return document


@pytest_asyncio.fixture
async def test_chat(async_session: AsyncSession, test_search_space):
    """Create a test chat."""
    from app.db import Chat

    chat = Chat(
        title=fake.sentence(),
        search_space_id=test_search_space.id,
    )

    async_session.add(chat)
    await async_session.commit()
    await async_session.refresh(chat)

    return chat


# ===========================
# Mock Service Fixtures
# ===========================


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = AsyncMock()
    mock.generate_response.return_value = "Mock LLM response"
    return mock


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    import numpy as np

    mock = AsyncMock()
    mock.get_embedding.return_value = np.random.rand(384).tolist()
    return mock


@pytest.fixture
def mock_connector_service():
    """Mock connector service for testing."""
    mock = AsyncMock()
    mock.search_connectors.return_value = []
    mock.stream_connector_results.return_value = AsyncMock()
    return mock


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock = MagicMock()
    mock.delay.return_value = MagicMock(id="test-task-id")
    mock.apply_async.return_value = MagicMock(id="test-task-id")
    return mock


# ===========================
# Data Generation Fixtures
# ===========================


@pytest.fixture
def faker_instance() -> Faker:
    """Provide Faker instance for test data generation."""
    return fake


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Generate sample user registration data."""
    return {
        "email": fake.email(),
        "password": "SecurePassword123!",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
    }


@pytest.fixture
def sample_search_space_data() -> dict[str, Any]:
    """Generate sample search space data."""
    return {
        "name": fake.word(),
        "description": fake.sentence(),
    }


@pytest.fixture
def sample_document_data() -> dict[str, Any]:
    """Generate sample document data."""
    return {
        "title": fake.sentence(),
        "content": fake.text(),
        "source": fake.url(),
    }


# ===========================
# Environment and Configuration Fixtures
# ===========================


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["ENVIRONMENT"] = "test"

    yield

    # Cleanup
    os.environ.pop("TESTING", None)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = True
    mock.incr.return_value = 1
    mock.expire.return_value = True
    return mock


# ===========================
# File Upload Fixtures
# ===========================


@pytest.fixture
def sample_pdf_file() -> bytes:
    """Generate a minimal valid PDF file for testing."""
    # Minimal PDF file structure
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
409
%%EOF"""


@pytest.fixture
def sample_text_file() -> bytes:
    """Generate a sample text file for testing."""
    return fake.text().encode("utf-8")
