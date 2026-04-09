"""Routes for exporting knowledge base content as ZIP."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search-spaces/{search_space_id}/export")
async def export_knowledge_base(
    search_space_id: int,
    folder_id: int | None = Query(None, description="Export only this folder's subtree"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Export documents as a ZIP of markdown files preserving folder structure.

    If folder_id is provided, only that folder's subtree is exported.
    Otherwise, the entire search space is exported.
    """
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to export documents in this search space",
    )

    # TODO: implement export logic
    return {"message": "Export endpoint placeholder"}
