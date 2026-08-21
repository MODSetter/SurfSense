"""Bridge the deletion routes to the transactional test session."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.auth.context import AuthContext
from app.db import User, get_async_session
from app.users import get_auth_context


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, db_user: User
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def enqueue_spy(monkeypatch) -> list[str]:
    """Capture the erase enqueue so the route needs no broker."""
    import app.routes.users_routes as routes

    enqueued: list[str] = []
    monkeypatch.setattr(
        routes.erase_account_task, "delay", lambda user_id: enqueued.append(user_id)
    )
    return enqueued
