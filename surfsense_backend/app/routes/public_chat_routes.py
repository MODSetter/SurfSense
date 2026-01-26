"""
Routes for public chat access (unauthenticated and mixed-auth endpoints).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.schemas.new_chat import (
    CloneInitiatedResponse,
    PublicChatResponse,
)
from app.services.public_chat_service import (
    get_public_chat,
    get_thread_by_share_token,
)
from app.users import current_active_user

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/{share_token}", response_model=PublicChatResponse)
async def read_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a public chat by share token.

    No authentication required.
    Returns sanitized content (citations stripped, non-UI tools removed).
    """
    return await get_public_chat(session, share_token)


@router.post("/{share_token}/clone", response_model=CloneInitiatedResponse)
async def clone_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Clone a public chat to the user's account.

    Requires authentication.
    Initiates a background job to copy the chat.
    """
    thread = await get_thread_by_share_token(session, share_token)

    if not thread:
        raise HTTPException(status_code=404, detail="Not found")

    # TODO: Implement Celery task for cloning
    # For now, return a placeholder response
    # The actual implementation will:
    # 1. Get user's default search space
    # 2. Queue Celery task to clone thread, messages, and podcasts
    # 3. Create notification on completion

    raise HTTPException(
        status_code=501,
        detail="Clone functionality not yet implemented",
    )
