"""Routes for exporting knowledge base content as ZIP."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Permission, User, get_async_session
from app.services.export_service import build_export_zip
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
    """Export documents as a ZIP of markdown files preserving folder structure."""
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to export documents in this search space",
    )

    try:
        result = await build_export_zip(session, search_space_id, folder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    def stream_and_cleanup():
        try:
            with open(result.zip_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        finally:
            os.unlink(result.zip_path)

    headers = {
        "Content-Disposition": f'attachment; filename="{result.export_name}.zip"',
        "Content-Length": str(result.zip_size),
    }

    if result.skipped_docs:
        headers["X-Skipped-Documents"] = str(len(result.skipped_docs))

    return StreamingResponse(
        stream_and_cleanup(),
        media_type="application/zip",
        headers=headers,
    )
