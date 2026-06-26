"""Integration tests for new-chat thread visibility invariants.

These tests exercise the route handlers directly with real DB-backed
users, memberships, and permissions. The important contract is that a
thread shared with a workspace stays shared across normal metadata
updates until the creator explicitly makes it private again.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    ChatVisibility,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    User,
)
from app.routes import new_chat_routes
from app.schemas.new_chat import (
    NewChatThreadCreate,
    NewChatThreadUpdate,
    NewChatThreadVisibilityUpdate,
)

pytestmark = pytest.mark.integration


def _auth(user: User) -> AuthContext:
    return AuthContext.session(user)


@pytest_asyncio.fixture
async def db_member(db_session: AsyncSession, db_workspace: Workspace) -> User:
    member = User(
        id=uuid.uuid4(),
        email="member@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(member)
    await db_session.flush()

    role = (
        (
            await db_session.execute(
                select(WorkspaceRole).where(
                    WorkspaceRole.workspace_id == db_workspace.id,
                    WorkspaceRole.name == "Editor",
                )
            )
        )
        .scalars()
        .one()
    )
    db_session.add(
        WorkspaceMembership(
            user_id=member.id,
            workspace_id=db_workspace.id,
            role_id=role.id,
            is_owner=False,
        )
    )
    await db_session.flush()
    return member


async def _create_thread(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    *,
    title: str = "Visibility Invariant Chat",
):
    return await new_chat_routes.create_thread(
        NewChatThreadCreate(
            title=title,
            archived=False,
            workspace_id=db_workspace.id,
            visibility=ChatVisibility.PRIVATE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )


def _active_thread_ids(response) -> set[int]:
    return {thread.id for thread in response.threads}


def _search_thread_ids(response) -> set[int]:
    return {thread.id for thread in response}


async def test_private_thread_is_hidden_from_other_workspace_member(
    db_session: AsyncSession,
    db_user: User,
    db_member: User,
    db_workspace: Workspace,
):
    thread = await _create_thread(db_session, db_user, db_workspace)

    member_threads = await new_chat_routes.list_threads(
        workspace_id=db_workspace.id,
        session=db_session,
        auth=_auth(db_member),
    )
    member_search = await new_chat_routes.search_threads(
        workspace_id=db_workspace.id,
        title="Visibility",
        session=db_session,
        auth=_auth(db_member),
    )

    assert thread.id not in _active_thread_ids(member_threads)
    assert thread.id not in _search_thread_ids(member_search)
    with pytest.raises(HTTPException) as exc_info:
        await new_chat_routes.get_thread_full(
            thread_id=thread.id,
            session=db_session,
            auth=_auth(db_member),
        )
    assert exc_info.value.status_code == 403


async def test_creator_can_share_thread_and_member_can_list_search_read_it(
    db_session: AsyncSession,
    db_user: User,
    db_member: User,
    db_workspace: Workspace,
):
    thread = await _create_thread(db_session, db_user, db_workspace)

    updated = await new_chat_routes.update_thread_visibility(
        thread_id=thread.id,
        visibility_update=NewChatThreadVisibilityUpdate(
            visibility=ChatVisibility.SEARCH_SPACE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )

    member_threads = await new_chat_routes.list_threads(
        workspace_id=db_workspace.id,
        session=db_session,
        auth=_auth(db_member),
    )
    member_search = await new_chat_routes.search_threads(
        workspace_id=db_workspace.id,
        title="Visibility",
        session=db_session,
        auth=_auth(db_member),
    )
    full_thread = await new_chat_routes.get_thread_full(
        thread_id=thread.id,
        session=db_session,
        auth=_auth(db_member),
    )

    assert updated.visibility == ChatVisibility.SEARCH_SPACE
    assert thread.id in _active_thread_ids(member_threads)
    assert thread.id in _search_thread_ids(member_search)
    assert full_thread["id"] == thread.id
    assert full_thread["visibility"] == ChatVisibility.SEARCH_SPACE


async def test_rename_and_archive_do_not_reset_shared_visibility(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    thread = await _create_thread(db_session, db_user, db_workspace)
    await new_chat_routes.update_thread_visibility(
        thread_id=thread.id,
        visibility_update=NewChatThreadVisibilityUpdate(
            visibility=ChatVisibility.SEARCH_SPACE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )

    renamed = await new_chat_routes.update_thread(
        thread_id=thread.id,
        thread_update=NewChatThreadUpdate(title="Renamed Shared Chat"),
        session=db_session,
        auth=_auth(db_user),
    )
    archived = await new_chat_routes.update_thread(
        thread_id=thread.id,
        thread_update=NewChatThreadUpdate(archived=True),
        session=db_session,
        auth=_auth(db_user),
    )

    assert renamed.visibility == ChatVisibility.SEARCH_SPACE
    assert archived.visibility == ChatVisibility.SEARCH_SPACE
    assert archived.archived is True


async def test_non_creator_cannot_change_shared_thread_back_to_private(
    db_session: AsyncSession,
    db_user: User,
    db_member: User,
    db_workspace: Workspace,
):
    thread = await _create_thread(db_session, db_user, db_workspace)
    await new_chat_routes.update_thread_visibility(
        thread_id=thread.id,
        visibility_update=NewChatThreadVisibilityUpdate(
            visibility=ChatVisibility.SEARCH_SPACE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )

    with pytest.raises(HTTPException) as exc_info:
        await new_chat_routes.update_thread_visibility(
            thread_id=thread.id,
            visibility_update=NewChatThreadVisibilityUpdate(
                visibility=ChatVisibility.PRIVATE,
            ),
            session=db_session,
            auth=_auth(db_member),
        )

    assert exc_info.value.status_code == 403


async def test_creator_can_make_shared_thread_private_again(
    db_session: AsyncSession,
    db_user: User,
    db_member: User,
    db_workspace: Workspace,
):
    thread = await _create_thread(db_session, db_user, db_workspace)
    await new_chat_routes.update_thread_visibility(
        thread_id=thread.id,
        visibility_update=NewChatThreadVisibilityUpdate(
            visibility=ChatVisibility.SEARCH_SPACE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )

    private_again = await new_chat_routes.update_thread_visibility(
        thread_id=thread.id,
        visibility_update=NewChatThreadVisibilityUpdate(
            visibility=ChatVisibility.PRIVATE,
        ),
        session=db_session,
        auth=_auth(db_user),
    )
    member_threads = await new_chat_routes.list_threads(
        workspace_id=db_workspace.id,
        session=db_session,
        auth=_auth(db_member),
    )
    member_search = await new_chat_routes.search_threads(
        workspace_id=db_workspace.id,
        title="Visibility",
        session=db_session,
        auth=_auth(db_member),
    )

    assert private_again.visibility == ChatVisibility.PRIVATE
    assert thread.id not in _active_thread_ids(member_threads)
    assert thread.id not in _search_thread_ids(member_search)
    with pytest.raises(HTTPException) as exc_info:
        await new_chat_routes.get_thread_full(
            thread_id=thread.id,
            session=db_session,
            auth=_auth(db_member),
        )
    assert exc_info.value.status_code == 403
