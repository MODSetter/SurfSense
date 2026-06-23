"""Regression tests for Zero's backend-computed authorization context."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import PersonalAccessToken, SearchSpace, User
from app.routes.search_spaces_routes import create_default_roles_and_membership
from app.utils.rbac import check_search_space_access, get_allowed_read_space_ids

pytestmark = pytest.mark.integration


def _pat_auth(user: User) -> AuthContext:
    pat = PersonalAccessToken(
        user_id=user.id,
        user=user,
        token_hash="1" * 64,
        token_prefix="ss_pat_zero",
        label="Zero PAT",
    )
    return AuthContext.pat_auth(user, pat)


async def _space_with_membership(
    db_session: AsyncSession,
    user: User,
    *,
    api_access_enabled: bool,
) -> SearchSpace:
    space = SearchSpace(
        name="Zero Authz Space",
        user_id=user.id,
        api_access_enabled=api_access_enabled,
    )
    db_session.add(space)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, space.id, user.id)
    await db_session.flush()
    return space


async def test_zero_read_set_matches_session_search_space_access(
    db_session: AsyncSession,
    db_user: User,
    db_search_space: SearchSpace,
):
    disabled_space = await _space_with_membership(
        db_session,
        db_user,
        api_access_enabled=False,
    )
    session_auth = AuthContext.session(db_user)

    allowed_ids = set(await get_allowed_read_space_ids(db_session, session_auth))

    for space in (db_search_space, disabled_space):
        membership = await check_search_space_access(db_session, session_auth, space.id)
        assert membership.search_space_id in allowed_ids


async def test_zero_read_set_applies_pat_api_access_gate(
    db_session: AsyncSession,
    db_user: User,
    db_search_space: SearchSpace,
):
    db_search_space.api_access_enabled = True
    disabled_space = await _space_with_membership(
        db_session,
        db_user,
        api_access_enabled=False,
    )
    await db_session.flush()
    pat_auth = _pat_auth(db_user)

    allowed_ids = set(await get_allowed_read_space_ids(db_session, pat_auth))

    assert db_search_space.id in allowed_ids
    assert disabled_space.id not in allowed_ids
    with pytest.raises(HTTPException) as exc_info:
        await check_search_space_access(db_session, pat_auth, disabled_space.id)
    assert exc_info.value.status_code == 403
