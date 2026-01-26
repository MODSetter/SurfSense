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
    Returns sanitized content (citations stripped).
    """
    return await get_public_chat(session, share_token)


@router.post("/{share_token}/clone", response_model=CloneInitiatedResponse)
async def clone_public_chat_endpoint(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Clone a public chat to the user's account.

    Requires authentication.
    Initiates a background job to copy the chat.
    """
    from app.tasks.celery_tasks.clone_chat_tasks import clone_public_chat_task

    thread = await get_thread_by_share_token(session, share_token)

    if not thread:
        raise HTTPException(status_code=404, detail="Not found")

    task_result = clone_public_chat_task.delay(
        share_token=share_token,
        user_id=str(user.id),
    )

    return CloneInitiatedResponse(
        status="processing",
        task_id=task_result.id,
        message="Copying chat to your account...",
    )
