"""
Routes for public chat access (unauthenticated and mixed-auth endpoints).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility, NewChatThread, User, get_async_session
from app.schemas.new_chat import (
    CloneInitResponse,
    PublicChatResponse,
)
from app.services.public_chat_service import (
    get_public_chat,
    get_thread_by_share_token,
    get_user_default_search_space,
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
    Returns sanitized content (citations stripped).
    """
    return await get_public_chat(session, share_token)


@router.post("/{share_token}/clone", response_model=CloneInitResponse)
async def clone_public_chat_endpoint(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Initialize cloning a public chat to the user's account.

    Creates an empty thread with clone_pending=True.
    Frontend should redirect to the new thread and call /complete-clone.

    Requires authentication.
    """
    source_thread = await get_thread_by_share_token(session, share_token)

    if not source_thread:
        raise HTTPException(status_code=404, detail="Chat not found or no longer public")

    target_search_space_id = await get_user_default_search_space(session, user.id)

    if target_search_space_id is None:
        raise HTTPException(status_code=400, detail="No search space found for user")

    new_thread = NewChatThread(
        title=source_thread.title,
        archived=False,
        visibility=ChatVisibility.PRIVATE,
        search_space_id=target_search_space_id,
        created_by_id=user.id,
        public_share_enabled=False,
        cloned_from_thread_id=source_thread.id,
        cloned_at=datetime.now(UTC),
        clone_pending=True,
    )
    session.add(new_thread)
    await session.commit()
    await session.refresh(new_thread)

    return CloneInitResponse(
        thread_id=new_thread.id,
        search_space_id=target_search_space_id,
        share_token=share_token,
    )
