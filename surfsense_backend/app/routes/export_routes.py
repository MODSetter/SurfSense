"""Routes for exporting knowledge base content as ZIP."""

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, get_async_session
from app.services.export_service import build_account_export_zip, build_export_zip
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export")
async def export_account(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Export every workspace the user can access as a contract-3 ZIP.

    The archive is built before the first byte is sent, so the build has a
    deadline: past it the user gets a sentence to act on, where a proxy that
    ran out of patience would only drop the connection.
    """
    deadline = config.ACCOUNT_EXPORT_TIMEOUT_SECONDS
    try:
        async with asyncio.timeout(deadline):
            result = await build_account_export_zip(session, auth.user.id)
    except TimeoutError:
        logger.error(
            "account export for user %s stopped after %ss", auth.user.id, deadline
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "The export was stopped because it took too long to build. "
                "Your data is still here and nothing was changed. Try again, "
                "and if it stops a second time write to us at /contact and "
                "we will send you the export."
            ),
        ) from None

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


@router.get("/workspaces/{workspace_id}/export")
async def export_knowledge_base(
    workspace_id: int,
    folder_id: int | None = Query(
        None, description="Export only this folder's subtree"
    ),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Export documents as a ZIP of markdown files preserving folder structure."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to export documents in this workspace",
    )

    try:
        result = await build_export_zip(session, workspace_id, folder_id)
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
