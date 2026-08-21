"""The server's own answer on whether an account may go."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace

pytestmark = pytest.mark.integration


async def test_deleting_is_refused_while_a_shared_workspace_is_unresolved(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    make_user,
    add_member,
    enqueue_spy: list[str],
):
    await add_member(db_workspace, await make_user())

    response = await client.delete("/users/me")

    assert response.status_code == 409
    blocked = response.json()["detail"]["workspaces"]
    assert [w["workspace_id"] for w in blocked] == [db_workspace.id]
    assert enqueue_spy == []
    assert db_user.is_active is True


async def test_deleting_locks_the_account_out_before_the_erase_is_queued(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    enqueue_spy: list[str],
):
    user_id = db_user.id

    response = await client.delete("/users/me")

    assert response.status_code == 204
    assert enqueue_spy == [str(user_id)]
    assert (
        await db_session.scalar(
            User.__table__.select()
            .with_only_columns(User.is_active)
            .where(User.id == user_id)
        )
        is False
    )
