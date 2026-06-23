"""Cookie-aware user profile routes."""

from fastapi import APIRouter, Depends, Request

from app.auth.context import AuthContext
from app.schemas import UserRead, UserUpdate
from app.users import UserManager, get_auth_context, get_user_manager, require_session_context

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    auth: AuthContext = Depends(get_auth_context),
):
    return auth.user


@router.patch("/me", response_model=UserRead)
async def update_current_user_profile(
    update: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_session_context),
    user_manager: UserManager = Depends(get_user_manager),
):
    updated_user = await user_manager.update(update, auth.user, safe=True, request=request)
    return updated_user
