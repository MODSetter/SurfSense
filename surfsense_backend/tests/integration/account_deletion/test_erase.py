"""Erasing the account, and what it must not take with it."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_deletion.erase import erase_account
from app.db import User, Workspace
from app.routes.workspaces_routes import create_default_roles_and_membership

pytestmark = pytest.mark.integration


@pytest.fixture
def bind_task_session(db_session: AsyncSession, monkeypatch) -> AsyncSession:
    """Hand the task bodies the test transaction instead of a fresh session."""

    def _make_session():
        @contextlib.asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            yield db_session

        return _ctx()

    for module in (
        "app.account_deletion.erase",
        "app.tasks.celery_tasks.document_tasks",
    ):
        monkeypatch.setattr(f"{module}.get_celery_session_maker", lambda: _make_session)
    return db_session


async def survives(session: AsyncSession, model, pk) -> bool:
    # Go to the database: the identity map still holds rows the erase removed.
    return await session.scalar(select(model.id).where(model.id == pk)) is not None


async def test_erasing_takes_the_account_and_the_workspaces_it_owned_alone(
    bind_task_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    make_user,
    add_member,
):
    host = await make_user()
    theirs = Workspace(name="Their Space", user_id=host.id)
    bind_task_session.add(theirs)
    await bind_task_session.flush()
    await create_default_roles_and_membership(bind_task_session, theirs.id, host.id)
    await add_member(theirs, db_user)
    user_id, mine, not_mine = db_user.id, db_workspace.id, theirs.id

    await erase_account(user_id)

    assert not await survives(bind_task_session, User, user_id)
    assert not await survives(bind_task_session, Workspace, mine)
    assert await survives(bind_task_session, Workspace, not_mine)


async def test_a_workspace_the_user_shares_goes_with_them(
    bind_task_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    make_user,
    add_member,
):
    colleague = await make_user()
    await add_member(db_workspace, colleague)
    user_id, workspace_id, colleague_id = db_user.id, db_workspace.id, colleague.id

    await erase_account(user_id)

    assert not await survives(bind_task_session, User, user_id)
    assert not await survives(bind_task_session, Workspace, workspace_id)
    # Their account is their own; only their access to this workspace ends.
    assert await survives(bind_task_session, User, colleague_id)


async def test_erasing_an_account_that_is_already_gone_finishes_quietly(
    bind_task_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    user_id = db_user.id

    await erase_account(user_id)
    await erase_account(user_id)

    assert not await survives(bind_task_session, User, user_id)
