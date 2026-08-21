"""What stands between a user and erasing themselves."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, Workspace, WorkspaceMembership


class Candidate(BaseModel):
    """A member who could take the workspace on."""

    user_id: UUID
    display_name: str | None
    email: str


class BlockingWorkspace(BaseModel):
    """An owned workspace that other people are still working in."""

    workspace_id: int
    name: str
    candidates: list[Candidate]


async def workspaces_blocking_deletion(
    session: AsyncSession, user_id: UUID
) -> list[BlockingWorkspace]:
    """Owned workspaces that would take other members' work down with them.

    Each carries its other members so the UI can offer a handover without
    asking again per workspace.
    """
    rows = await session.execute(
        select(Workspace.id, Workspace.name, User.id, User.display_name, User.email)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(Workspace.user_id == user_id, WorkspaceMembership.user_id != user_id)
        .order_by(Workspace.id, User.email)
    )

    blocking: dict[int, BlockingWorkspace] = {}
    for workspace_id, name, member_id, display_name, email in rows:
        blocking.setdefault(
            workspace_id,
            BlockingWorkspace(workspace_id=workspace_id, name=name, candidates=[]),
        ).candidates.append(
            Candidate(user_id=member_id, display_name=display_name, email=email)
        )
    return list(blocking.values())
