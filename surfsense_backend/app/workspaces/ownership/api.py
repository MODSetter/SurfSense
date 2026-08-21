"""HTTP door for handing a workspace over."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import require_session_context
from app.workspaces.ownership.transfer import transfer_ownership

router = APIRouter()


class TransferOwnership(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_owner_id: UUID


@router.post(
    "/workspaces/{workspace_id}/transfer-ownership",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def transfer_workspace_ownership(
    workspace_id: int,
    payload: TransferOwnership,
    session: AsyncSession = Depends(get_async_session),
    # Session-only: giving a workspace away should not be reachable with a
    # leaked personal access token.
    auth: AuthContext = Depends(require_session_context),
) -> None:
    """Make another member the owner of a workspace you own."""
    await transfer_ownership(
        session,
        workspace_id=workspace_id,
        new_owner_id=payload.new_owner_id,
        current_owner_id=auth.user.id,
    )
    await session.commit()
