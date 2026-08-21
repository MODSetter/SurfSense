"""What stands between a user and erasing themselves."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_deletion.preflight import workspaces_blocking_deletion
from app.db import User, Workspace
from app.routes.workspaces_routes import create_default_roles_and_membership

pytestmark = pytest.mark.integration


async def test_a_workspace_the_user_owns_alone_does_not_block_deletion(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    assert await workspaces_blocking_deletion(db_session, db_user.id) == []


async def test_an_owned_workspace_with_another_member_blocks_and_names_them(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    make_user,
    add_member,
):
    colleague = await make_user()
    colleague.display_name = "Colleague"
    await add_member(db_workspace, colleague)

    blocking = await workspaces_blocking_deletion(db_session, db_user.id)

    assert [w.workspace_id for w in blocking] == [db_workspace.id]
    assert blocking[0].name == db_workspace.name
    assert [(c.user_id, c.display_name, c.email) for c in blocking[0].candidates] == [
        (colleague.id, "Colleague", colleague.email)
    ]


async def test_someone_elses_shared_workspace_is_not_the_users_problem(
    db_session: AsyncSession,
    db_user: User,
    make_user,
    add_member,
):
    owner = await make_user()
    theirs = Workspace(name="Their Space", user_id=owner.id)
    db_session.add(theirs)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, theirs.id, owner.id)
    await add_member(theirs, db_user)

    assert await workspaces_blocking_deletion(db_session, db_user.id) == []
