"""
Report routes for CRUD operations and export (PDF/DOCX).

These routes support the report generation feature in new-chat.
Reports are generated inline by the agent tool and stored as Markdown.
Export to PDF/DOCX is on-demand via pypandoc.

Authorization: lightweight search-space membership checks (no granular RBAC)
since reports are chat-generated artifacts, not standalone managed resources.
"""

import asyncio
import io
import logging
from enum import Enum

import pypandoc
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Report,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import ReportContentRead, ReportRead
from app.users import current_active_user
from app.utils.rbac import check_search_space_access

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_REPORT_LIST_LIMIT = 500


class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_report_with_access(
    report_id: int,
    session: AsyncSession,
    user: User,
) -> Report:
    """Fetch a report and verify the user belongs to its search space.

    Raises HTTPException(404) if not found, HTTPException(403) if no access.
    """
    result = await session.execute(select(Report).filter(Report.id == report_id))
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Lightweight membership check – no granular RBAC, just "is the user a
    # member of the search space this report belongs to?"
    await check_search_space_access(session, user, report.search_space_id)

    return report


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/reports", response_model=list[ReportRead])
async def read_reports(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=MAX_REPORT_LIST_LIMIT),
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List reports the user has access to.
    Filters by search space membership.
    """
    try:
        if search_space_id is not None:
            # Verify the caller is a member of the requested search space
            await check_search_space_access(session, user, search_space_id)

            result = await session.execute(
                select(Report)
                .filter(Report.search_space_id == search_space_id)
                .order_by(Report.id.desc())
                .offset(skip)
                .limit(limit)
            )
        else:
            result = await session.execute(
                select(Report)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .order_by(Report.id.desc())
                .offset(skip)
                .limit(limit)
            )
        return result.scalars().all()
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching reports"
        ) from None


@router.get("/reports/{report_id}", response_model=ReportRead)
async def read_report(
    report_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific report by ID (metadata only, no content).
    """
    try:
        return await _get_report_with_access(report_id, session, user)
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching report"
        ) from None


@router.get("/reports/{report_id}/content", response_model=ReportContentRead)
async def read_report_content(
    report_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get full Markdown content of a report.
    """
    try:
        return await _get_report_with_access(report_id, session, user)
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching report content",
        ) from None


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: int,
    format: ExportFormat = Query(ExportFormat.PDF, description="Export format: pdf or docx"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Export a report as PDF or DOCX.
    """
    try:
        report = await _get_report_with_access(report_id, session, user)

        if not report.content:
            raise HTTPException(
                status_code=400, detail="Report has no content to export"
            )

        # Convert Markdown to the requested format via pypandoc.
        # pypandoc spawns a pandoc subprocess (blocking), so we run it in a
        # thread executor to avoid blocking the async event loop.
        extra_args = ["--standalone"]
        if format == ExportFormat.PDF:
            extra_args.append("--pdf-engine=weasyprint")

        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(
            None,  # default thread-pool
            lambda: pypandoc.convert_text(
                report.content,
                format.value,
                format="md",
                extra_args=extra_args,
            ),
        )

        # pypandoc returns bytes for binary formats (pdf, docx), str for text formats
        if isinstance(output, str):
            output = output.encode("utf-8")

        # Sanitize filename
        safe_title = (
            "".join(c if c.isalnum() or c in " -_" else "_" for c in report.title)
            .strip()[:80]
            or "report"
        )

        media_types = {
            ExportFormat.PDF: "application/pdf",
            ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        return StreamingResponse(
            io.BytesIO(output),
            media_type=media_types[format],
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.{format.value}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Report export failed")
        raise HTTPException(
            status_code=500, detail=f"Export failed: {e!s}"
        ) from e


@router.delete("/reports/{report_id}", response_model=dict)
async def delete_report(
    report_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a report.
    """
    try:
        db_report = await _get_report_with_access(report_id, session, user)

        await session.delete(db_report)
        await session.commit()
        return {"message": "Report deleted successfully"}
    except HTTPException:
        raise
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error occurred while deleting report"
        ) from None
