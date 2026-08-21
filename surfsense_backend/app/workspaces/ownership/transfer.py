"""Handing a workspace to one of its members."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, WorkspaceMembership, WorkspaceRole
from app.exceptions import ForbiddenError, ValidationError


async def transfer_ownership(
    session: AsyncSession,
    *,
    workspace_id: int,
    new_owner_id: UUID,
    current_owner_id: UUID,
) -> None:
    """Make a member the owner and step the former owner down to Editor.

    Leaves the transaction open so a caller deleting their account can hand
    over several workspaces and erase itself as one unit.
    """
    former_owner = await _membership(session, workspace_id, current_owner_id)
    if former_owner is None or not former_owner.is_owner:
        raise ForbiddenError("Only the workspace owner can transfer ownership.")

    new_owner = await _membership(session, workspace_id, new_owner_id)
    if new_owner is None:
        # Handing it to a stranger would need an invite, which is its own flow.
        raise ValidationError(
            "The new owner must already be a member of this workspace."
        )

    # Ownership is recorded in three places, and any one of them left behind
    # gives the workspace two owners or none.
    await session.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(user_id=new_owner_id)
    )
    new_owner.is_owner = True
    new_owner.role_id = await _role_id(session, workspace_id, "Owner")
    former_owner.is_owner = False
    former_owner.role_id = await _role_id(session, workspace_id, "Editor")
    await session.flush()


async def _membership(
    session: AsyncSession, workspace_id: int, user_id: UUID
) -> WorkspaceMembership | None:
    return await session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )


async def _role_id(session: AsyncSession, workspace_id: int, name: str) -> int:
    # Seeded for every workspace as a system role, so absence would be a bug
    # worth crashing on rather than a membership silently left role-less.
    return await session.scalar(
        select(WorkspaceRole.id).where(
            WorkspaceRole.workspace_id == workspace_id,
            WorkspaceRole.name == name,
        )
    )
