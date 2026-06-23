"""Composio route integration fixtures.

The `composio` sys.modules hijack lives in the parent integration conftest
so it runs before any sibling suite imports `app.routes`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = pytest.mark.integration

limiter.enabled = False
config.COMPOSIO_ENABLED = True
config.COMPOSIO_API_KEY = "e2e-integration-composio-sentinel"
config.NEXT_FRONTEND_URL = "http://localhost:3000"


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def drive_connector(
    db_session: AsyncSession,
    db_user: User,
    db_search_space,
) -> SearchSourceConnector:
    connector = SearchSourceConnector(
        name="Google Drive (Composio) - e2e-fake@surfsense.example",
        connector_type=SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        is_indexable=True,
        config={
            "composio_connected_account_id": "fake-acct-googledrive-existing",
            "toolkit_id": "googledrive",
            "toolkit_name": "Google Drive",
            "is_indexable": True,
        },
        search_space_id=db_search_space.id,
        user_id=db_user.id,
    )
    db_session.add(connector)
    await db_session.flush()
    return connector
