"""Zero sync authentication context routes."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import get_auth_context
from app.utils.rbac import get_allowed_read_space_ids

router = APIRouter(prefix="/zero", tags=["zero"])


class ZeroContextResponse(BaseModel):
    userId: str
    allowedSpaceIds: list[int]


@router.get("/context", response_model=ZeroContextResponse)
async def get_zero_context(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZeroContextResponse:
    allowed_space_ids = await get_allowed_read_space_ids(session, auth)
    return ZeroContextResponse(
        userId=str(auth.user.id),
        allowedSpaceIds=allowed_space_ids,
    )
