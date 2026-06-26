"""Zero sync authentication context routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.users import get_auth_context
from app.utils.rbac import get_allowed_read_space_ids

router = APIRouter(prefix="/zero", tags=["zero"])


class ZeroContextResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    allowed_space_ids: list[int] = Field(alias="allowedSpaceIds")


@router.get("/context", response_model=ZeroContextResponse)
async def get_zero_context(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ZeroContextResponse:
    allowed_space_ids = await get_allowed_read_space_ids(session, auth)
    return ZeroContextResponse(
        user_id=str(auth.user.id),
        allowed_space_ids=allowed_space_ids,
    )
