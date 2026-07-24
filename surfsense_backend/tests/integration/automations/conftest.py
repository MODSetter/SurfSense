"""Shared fixtures for automations integration tests.

Bridges the code-under-test to the transactional ``db_session`` so real
behavior runs against real Postgres and rolls back at test end:

* ``client`` — httpx over ASGI with ``get_async_session``/``get_auth_context``
  overridden to the test session + owner.
* ``enqueue_spy`` — capture ``automation_run_execute.apply_async`` so run-now
  can be asserted without a Redis broker.
"""

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
            follow_redirects=False,
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture
def enqueue_spy(monkeypatch) -> list[dict]:
    """Capture Celery enqueues so run-now needs no broker."""
    import app.automations.dispatch.launch as launch_mod

    calls: list[dict] = []

    def _spy(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return None

    monkeypatch.setattr(launch_mod.automation_run_execute, "apply_async", _spy)
    return calls
