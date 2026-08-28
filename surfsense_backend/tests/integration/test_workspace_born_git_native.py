"""A new workspace inherits the global git-native switch at creation.

The flag must survive a real INSERT round-trip, not merely live on the transient
ORM object — so this exercises the route against a real database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.auth.context import AuthContext
from app.config import config as app_config
from app.db import Workspace
from app.routes import workspaces_routes
from app.schemas import WorkspaceCreate
from app.users import create_default_workspace

pytestmark = pytest.mark.integration


async def _persisted_flag(db_session, workspace_id: int) -> bool:
    db_session.expire_all()
    return await db_session.scalar(
        select(Workspace.knowledge_store_enabled).where(Workspace.id == workspace_id)
    )


async def test_new_workspace_persists_git_native_when_global_enabled(
    db_session, db_user, monkeypatch
):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)

    response = await workspaces_routes.create_workspace(
        WorkspaceCreate(name="Born git-native", description=""),
        session=db_session,
        auth=AuthContext.session(db_user),
    )

    assert await _persisted_flag(db_session, response.id) is True


async def test_new_workspace_persists_legacy_when_global_disabled(
    db_session, db_user, monkeypatch
):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)

    response = await workspaces_routes.create_workspace(
        WorkspaceCreate(name="Stays legacy", description=""),
        session=db_session,
        auth=AuthContext.session(db_user),
    )

    assert await _persisted_flag(db_session, response.id) is False


async def test_signup_default_workspace_born_git_native_when_global_enabled(
    db_session, db_user, monkeypatch
):
    """The signup path creates its own workspace and must honour the switch too."""
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)

    workspace = await create_default_workspace(db_session, db_user)

    assert await _persisted_flag(db_session, workspace.id) is True


async def test_signup_default_workspace_stays_legacy_when_global_disabled(
    db_session, db_user, monkeypatch
):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)

    workspace = await create_default_workspace(db_session, db_user)

    assert await _persisted_flag(db_session, workspace.id) is False
