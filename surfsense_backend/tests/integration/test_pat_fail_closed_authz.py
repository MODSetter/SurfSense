"""Runtime smoke tests for fail-closed PAT authorization primitives."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import PersonalAccessToken, Workspace, User
from app.users import allow_any_principal, require_session_context
from app.utils.rbac import check_workspace_access

pytestmark = pytest.mark.integration


def _pat_auth(user: User) -> AuthContext:
    pat = PersonalAccessToken(
        user_id=user.id,
        user=user,
        token_hash="0" * 64,
        token_prefix="ss_pat_test",
        label="Test PAT",
    )
    return AuthContext.pat_auth(user, pat)


async def test_pat_is_rejected_by_session_only_dependency(db_user: User):
    auth = _pat_auth(db_user)

    with pytest.raises(HTTPException) as exc_info:
        await require_session_context(auth=auth)

    assert exc_info.value.status_code == 403


async def test_pat_is_allowed_by_bootstrap_dependency(db_user: User):
    auth = _pat_auth(db_user)

    assert await allow_any_principal(auth=auth) is auth


async def test_pat_is_rejected_for_api_disabled_space(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    db_workspace.api_access_enabled = False
    await db_session.flush()
    auth = _pat_auth(db_user)

    with pytest.raises(HTTPException) as exc_info:
        await check_workspace_access(db_session, auth, db_workspace.id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "API access is not enabled for this workspace."


async def test_pat_is_allowed_for_api_enabled_space(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    db_workspace.api_access_enabled = True
    await db_session.flush()
    auth = _pat_auth(db_user)

    membership = await check_workspace_access(db_session, auth, db_workspace.id)

    assert membership.user_id == db_user.id
    assert membership.workspace_id == db_workspace.id
