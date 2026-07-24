from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routes import workspaces_routes
from app.schemas import WorkspaceCreate

pytestmark = pytest.mark.unit


class _CountResult:
    def __init__(self, count: int):
        self.count = count

    def scalar_one(self) -> int:
        return self.count


class _FakeSession:
    def __init__(self, owned_count: int):
        self.owned_count = owned_count

    async def execute(self, _statement):
        return _CountResult(self.owned_count)


@pytest.mark.asyncio
async def test_read_workspace_limits_uses_backend_config(monkeypatch):
    monkeypatch.setattr(
        workspaces_routes.config,
        "MAX_WORKSPACES_PER_USER",
        37,
        raising=False,
    )

    result = await workspaces_routes.read_workspace_limits(_auth=SimpleNamespace())

    assert result == {"max_workspaces_per_user": 37}


@pytest.mark.asyncio
async def test_create_workspace_rejects_when_owned_limit_reached(monkeypatch):
    monkeypatch.setattr(
        workspaces_routes.config,
        "MAX_WORKSPACES_PER_USER",
        2,
        raising=False,
    )
    auth = SimpleNamespace(user=SimpleNamespace(id="user-1"))
    session = _FakeSession(owned_count=2)

    with pytest.raises(HTTPException) as exc_info:
        await workspaces_routes.create_workspace(
            WorkspaceCreate(name="Extra", description=""),
            session=session,
            auth=auth,
        )

    assert exc_info.value.status_code == 409
    assert "at most 2 workspaces" in exc_info.value.detail
