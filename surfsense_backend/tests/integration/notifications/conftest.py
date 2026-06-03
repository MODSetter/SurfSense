"""Notifications integration fixtures.

The app's DB session and current-user dependencies are overridden to ride the
test's transactional `db_session`, so API calls and seeded rows share one
transaction that rolls back per test. Overriding `current_active_user` also
bypasses real JWT auth, so these tests don't depend on AUTH_TYPE.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.db import User, get_async_session
from app.users import current_active_user

pytestmark = pytest.mark.integration

limiter.enabled = False


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_user() -> User:
        return db_user

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[current_active_user] = override_user

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
