"""Handing a workspace to someone else moves every trace of ownership."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace, WorkspaceMembership, WorkspaceRole
from app.exceptions import ForbiddenError, ValidationError
from app.workspaces.ownership.transfer import transfer_ownership

pytestmark = pytest.mark.integration


async def make_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def role_named(session: AsyncSession, workspace: Workspace, name: str) -> int:
    role = (
        (
            await session.execute(
                select(WorkspaceRole).where(
                    WorkspaceRole.workspace_id == workspace.id,
                    WorkspaceRole.name == name,
                )
            )
        )
        .scalars()
        .one()
    )
    return role.id


async def join(
    session: AsyncSession, workspace: Workspace, user: User, role_name: str
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=workspace.id,
        role_id=await role_named(session, workspace, role_name),
        is_owner=False,
    )
    session.add(membership)
    await session.flush()
    return membership


async def membership_of(
    session: AsyncSession, workspace: Workspace, user: User
) -> WorkspaceMembership:
    return (
        (
            await session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.user_id == user.id,
                )
            )
        )
        .scalars()
        .one()
    )


async def test_the_recipient_becomes_the_owner_and_the_sender_becomes_an_editor(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    recipient = await make_user(db_session)
    await join(db_session, db_workspace, recipient, "Viewer")

    await transfer_ownership(
        db_session,
        workspace_id=db_workspace.id,
        new_owner_id=recipient.id,
        current_owner_id=db_user.id,
    )

    await db_session.refresh(db_workspace)
    new_owner = await membership_of(db_session, db_workspace, recipient)
    former_owner = await membership_of(db_session, db_workspace, db_user)

    assert db_workspace.user_id == recipient.id
    assert new_owner.is_owner is True
    assert new_owner.role_id == await role_named(db_session, db_workspace, "Owner")
    assert former_owner.is_owner is False
    assert former_owner.role_id == await role_named(db_session, db_workspace, "Editor")


async def test_a_member_who_is_not_the_owner_cannot_give_the_workspace_away(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    editor = await make_user(db_session)
    await join(db_session, db_workspace, editor, "Editor")
    accomplice = await make_user(db_session)
    await join(db_session, db_workspace, accomplice, "Viewer")

    with pytest.raises(ForbiddenError):
        await transfer_ownership(
            db_session,
            workspace_id=db_workspace.id,
            new_owner_id=accomplice.id,
            current_owner_id=editor.id,
        )

    assert (await membership_of(db_session, db_workspace, db_user)).is_owner is True


async def test_the_workspace_cannot_be_handed_to_someone_who_is_not_a_member(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    stranger = await make_user(db_session)

    with pytest.raises(ValidationError):
        await transfer_ownership(
            db_session,
            workspace_id=db_workspace.id,
            new_owner_id=stranger.id,
            current_owner_id=db_user.id,
        )

    assert (await membership_of(db_session, db_workspace, db_user)).is_owner is True
