"""Cookie-aware user profile routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.account_deletion.erase import erase_account_task
from app.auth.context import AuthContext
from app.auth.session_cookies import clear_session
from app.db import User, get_async_session
from app.schemas import UserRead, UserUpdate
from app.users import (
    UserManager,
    get_auth_context,
    get_user_manager,
    require_session_context,
)
from app.utils.refresh_tokens import revoke_all_user_tokens

logger = logging.getLogger(__name__)

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
    updated_user = await user_manager.update(
        update, auth.user, safe=True, request=request
    )
    return updated_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user_account(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    # Session-only: a leaked personal access token must not be able to
    # destroy the account it was issued from.
    auth: AuthContext = Depends(require_session_context),
):
    """Lock the account out now; erase it in the background."""
    # Deactivating is the whole lockout: get_auth_context already turns away
    # inactive users on both the session and the token path.
    await session.execute(
        update(User).where(User.id == auth.user.id).values(is_active=False)
    )
    await session.commit()
    await revoke_all_user_tokens(auth.user.id)

    try:
        erase_account_task.delay(str(auth.user.id))
    except Exception as dispatch_error:
        # Otherwise the account is locked out of a deletion that never runs.
        await session.execute(
            update(User).where(User.id == auth.user.id).values(is_active=True)
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not start account deletion. Please try again.",
        ) from dispatch_error

    clear_session(response, request)
    logger.info("Account %s deactivated and queued for erasure", auth.user.id)
