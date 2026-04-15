"""
Report routes for read, update, export, and delete operations.

Reports are generated inline by the agent tool during chat and stored as
Markdown in the database.  Users can edit report content via the Plate editor
and save changes through the PUT endpoint.
Export is on-demand in multiple formats (PDF, DOCX, HTML, LaTeX, EPUB, ODT,
plain text).  PDF uses pypandoc (Markdown->Typst) + typst-py; the rest use
pypandoc directly with format-specific templates and options.

Authorization: lightweight search-space membership checks (no granular RBAC)
since reports are chat-generated artifacts, not standalone managed resources.
"""

import asyncio
import io
import logging
import os
import re
import tempfile
from enum import StrEnum

import pypandoc
import typst
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
from app.schemas import ReportContentRead, ReportContentUpdate, ReportRead
from app.schemas.reports import ReportVersionInfo
from app.templates.export_helpers import (
    get_html_css_path,
    get_reference_docx_path,
    get_typst_template_path,
)
from app.users import current_active_user
from app.utils.rbac import check_search_space_access

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_REPORT_LIST_LIMIT = 500


class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    LATEX = "latex"
    EPUB = "epub"
    ODT = "odt"
    PLAIN = "plain"


_MEDIA_TYPES: dict[ExportFormat, str] = {
    ExportFormat.PDF: "application/pdf",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ExportFormat.HTML: "text/html; charset=utf-8",
    ExportFormat.LATEX: "application/x-tex",
    ExportFormat.EPUB: "application/epub+zip",
    ExportFormat.ODT: "application/vnd.oasis.opendocument.text",
    ExportFormat.PLAIN: "text/plain; charset=utf-8",
}

_FILE_EXTENSIONS: dict[ExportFormat, str] = {
    ExportFormat.PDF: "pdf",
    ExportFormat.DOCX: "docx",
    ExportFormat.HTML: "html",
    ExportFormat.LATEX: "tex",
    ExportFormat.EPUB: "epub",
    ExportFormat.ODT: "odt",
    ExportFormat.PLAIN: "txt",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n", re.MULTILINE)


def _strip_wrapping_code_fences(text: str) -> str:
    """Remove wrapping code fences (```markdown...```) that LLMs often add."""
    stripped = text.strip()
    m = _CODE_FENCE_RE.match(stripped)
    if m and stripped.endswith("```"):
        stripped = stripped[m.end() : -3].rstrip()
    return stripped


def _normalize_latex_delimiters(text: str) -> str:
    """Convert all LaTeX math delimiters to dollar-sign form.

    Pandoc's ``tex_math_dollars`` extension (on the ``gfm`` reader) handles
    ``$…$`` and ``$$…$$`` natively.  This function converts every other
    delimiter style that LLMs produce into dollar-sign form so pandoc can
    parse them as math.

    Supported conversions:
      \\[…\\]                                → $$…$$  (display math)
      \\(…\\)                                → $…$    (inline math)
      \\begin{equation}…\\end{equation}      → $$…$$  (display math)
      \\begin{displaymath}…\\end{displaymath}→ $$…$$  (display math)
      \\begin{math}…\\end{math}              → $…$    (inline math)
      `$$…$$` / `$…$`                        → strip wrapping backticks
    """
    # 1. Block math: \[...\] → $$...$$
    text = re.sub(r"\\\[([\s\S]*?)\\\]", lambda m: f"$${m.group(1)}$$", text)
    # 2. Inline math: \(...\) → $...$
    text = re.sub(r"\\\(([\s\S]*?)\\\)", lambda m: f"${m.group(1)}$", text)
    # 3. \begin{equation}...\end{equation} → $$...$$
    text = re.sub(
        r"\\begin\{equation\}([\s\S]*?)\\end\{equation\}",
        lambda m: f"$${m.group(1)}$$",
        text,
    )
    # 4. \begin{displaymath}...\end{displaymath} → $$...$$
    text = re.sub(
        r"\\begin\{displaymath\}([\s\S]*?)\\end\{displaymath\}",
        lambda m: f"$${m.group(1)}$$",
        text,
    )
    # 5. \begin{math}...\end{math} → $...$
    text = re.sub(
        r"\\begin\{math\}([\s\S]*?)\\end\{math\}",
        lambda m: f"${m.group(1)}$",
        text,
    )
    # 6. Strip backtick wrapping around math: `$$...$$` → $$...$$ and `$...$` → $...$
    text = re.sub(r"`(\${1,2})((?:(?!\1).)+)\1`", r"\1\2\1", text)

    # 7. Trim whitespace inside inline math $...$.
    #    Pandoc's tex_math_dollars requires NO space after the opening $ and
    #    NO space before the closing $.  LLMs frequently produce "$ e^x $"
    #    or "\( e^x \)" (which step 2 converts to "$ e^x $").  Without
    #    trimming, pandoc treats these as literal dollar-sign text.
    #    We require spaces on BOTH sides to avoid false-positives on
    #    currency like "$50" or "$50 and $100".
    def _trim_inline_math(m: re.Match) -> str:
        inner = m.group(1).strip()
        return f"${inner}$" if inner else m.group(0)

    text = re.sub(r"(?<!\$)\$(?!\$) +(.+?) +\$(?!\$)", _trim_inline_math, text)
    return text


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

    # Lightweight membership check - no granular RBAC, just "is the user a
    # member of the search space this report belongs to?"
    await check_search_space_access(session, user, report.search_space_id)

    return report


async def _get_version_siblings(
    session: AsyncSession,
    report: Report,
) -> list[ReportVersionInfo]:
    """Get all versions in the same report group, ordered by created_at."""
    if not report.report_group_id:
        # Legacy report without group — it's the only version
        return [ReportVersionInfo(id=report.id, created_at=report.created_at)]

    result = await session.execute(
        select(Report.id, Report.created_at)
        .filter(Report.report_group_id == report.report_group_id)
        .order_by(Report.created_at.asc())
    )
    rows = result.all()
    return [ReportVersionInfo(id=row[0], created_at=row[1]) for row in rows]


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
    Get full Markdown content of a report, including version siblings.
    """
    try:
        report = await _get_report_with_access(report_id, session, user)
        versions = await _get_version_siblings(session, report)

        return ReportContentRead(
            id=report.id,
            title=report.title,
            content=report.content,
            content_type=report.content_type,
            report_metadata=report.report_metadata,
            report_group_id=report.report_group_id,
            versions=versions,
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching report content",
        ) from None


@router.put("/reports/{report_id}/content", response_model=ReportContentRead)
async def update_report_content(
    report_id: int,
    body: ReportContentUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update the Markdown content of a report.

    The caller must be a member of the search space the report belongs to.
    Returns the updated report content including version siblings.
    """
    try:
        report = await _get_report_with_access(report_id, session, user)

        report.content = body.content
        session.add(report)
        await session.commit()
        await session.refresh(report)

        versions = await _get_version_siblings(session, report)

        return ReportContentRead(
            id=report.id,
            title=report.title,
            content=report.content,
            content_type=report.content_type,
            report_metadata=report.report_metadata,
            report_group_id=report.report_group_id,
            versions=versions,
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while updating report content",
        ) from None


@router.get("/reports/{report_id}/preview")
async def preview_report_pdf(
    report_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Return a compiled PDF preview for Typst-based reports (resumes).

    Reads the Typst source from the database and compiles it to PDF bytes
    on-the-fly. Only works for reports with content_type='typst'.
    """
    try:
        report = await _get_report_with_access(report_id, session, user)

        if not report.content:
            raise HTTPException(
                status_code=400, detail="Report has no content to preview"
            )

        if report.content_type != "typst":
            raise HTTPException(
                status_code=400,
                detail="Preview is only available for Typst-based reports",
            )

        def _compile() -> bytes:
            return typst.compile(report.content.encode("utf-8"))

        pdf_bytes = await asyncio.to_thread(_compile)

        safe_title = re.sub(r"[^\w\s-]", "", report.title or "Resume").strip()
        filename = f"{safe_title}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to compile Typst preview for report %d", report_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to compile resume preview",
        ) from None


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: int,
    format: ExportFormat = Query(
        ExportFormat.PDF,
        description="Export format: pdf, docx, html, latex, epub, odt, or plain",
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Export a report in the requested format.
    """
    try:
        report = await _get_report_with_access(report_id, session, user)

        if not report.content:
            raise HTTPException(
                status_code=400, detail="Report has no content to export"
            )

        # Typst-based reports (resumes): compile directly without Pandoc
        if report.content_type == "typst":
            if format != ExportFormat.PDF:
                raise HTTPException(
                    status_code=400,
                    detail="Typst-based reports currently only support PDF export",
                )

            def _compile_typst() -> bytes:
                return typst.compile(report.content.encode("utf-8"))

            pdf_bytes = await asyncio.to_thread(_compile_typst)
            safe_title = re.sub(r"[^\w\s-]", "", report.title or "Resume").strip()
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_title}.pdf"',
                },
            )

        # Strip wrapping code fences that LLMs sometimes add around Markdown.
        # Without this, pandoc treats the entire content as a code block.
        markdown_content = _strip_wrapping_code_fences(report.content)

        # Normalise all LaTeX math delimiters (\(\), \[\], \begin{equation},
        # etc.) into $/$$ form that pandoc's tex_math_dollars extension can parse.
        markdown_content = _normalize_latex_delimiters(markdown_content)

        # Use "gfm" as the base input format because LLM output uses GFM-style
        # pipe tables that pandoc's stricter default "markdown" may mangle.
        # The +tex_math_dollars extension enables $/$$ math recognition.

        formatted_date = report.created_at.strftime("%B %d, %Y")
        report_title = report.title or "Report"
        input_fmt = "gfm+tex_math_dollars"
        meta_args = ["-M", f"title:{report_title}", "-M", f"date:{formatted_date}"]

        def _convert_and_read() -> bytes:
            """Run all blocking I/O in a thread."""

            # -- PDF: Markdown -> Typst markup -> typst-py -> PDF bytes ------
            if format == ExportFormat.PDF:
                typst_template = str(get_typst_template_path())
                typst_markup: str = pypandoc.convert_text(
                    markdown_content,
                    "typst",
                    format=input_fmt,
                    extra_args=[
                        "--standalone",
                        f"--template={typst_template}",
                        "-V",
                        "mainfont:Libertinus Serif",
                        "-V",
                        "codefont:DejaVu Sans Mono",
                        *meta_args,
                    ],
                )
                return typst.compile(typst_markup.encode("utf-8"))

            # -- DOCX: styled reference doc ----------------------------------
            if format == ExportFormat.DOCX:
                return _pandoc_to_tempfile(
                    format.value,
                    [
                        "--standalone",
                        f"--reference-doc={get_reference_docx_path()}",
                        *meta_args,
                    ],
                )

            # -- HTML: self-contained with custom CSS ------------------------
            if format == ExportFormat.HTML:
                html_str: str = pypandoc.convert_text(
                    markdown_content,
                    "html5",
                    format=input_fmt,
                    extra_args=[
                        "--standalone",
                        "--embed-resources",
                        f"--css={get_html_css_path()}",
                        "--syntax-highlighting=pygments",
                        *meta_args,
                    ],
                )
                return html_str.encode("utf-8")

            # -- EPUB: binary output via tempfile ----------------------------
            if format == ExportFormat.EPUB:
                return _pandoc_to_tempfile("epub3", ["--standalone", *meta_args])

            # -- ODT: binary output via tempfile -----------------------------
            if format == ExportFormat.ODT:
                return _pandoc_to_tempfile("odt", ["--standalone", *meta_args])

            # -- LaTeX: text output ------------------------------------------
            if format == ExportFormat.LATEX:
                tex_str: str = pypandoc.convert_text(
                    markdown_content,
                    "latex",
                    format=input_fmt,
                    extra_args=["--standalone", *meta_args],
                )
                return tex_str.encode("utf-8")

            # -- Plain text: text output -------------------------------------
            plain_str: str = pypandoc.convert_text(
                markdown_content,
                "plain",
                format=input_fmt,
                extra_args=["--wrap=auto", "--columns=80"],
            )
            return plain_str.encode("utf-8")

        def _pandoc_to_tempfile(output_format: str, extra_args: list[str]) -> bytes:
            """Convert via pandoc to a binary format using a temp file."""
            fd, tmp_path = tempfile.mkstemp(suffix=f".{output_format}")
            os.close(fd)
            try:
                pypandoc.convert_text(
                    markdown_content,
                    output_format,
                    format=input_fmt,
                    extra_args=extra_args,
                    outputfile=tmp_path,
                )
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                os.unlink(tmp_path)

        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, _convert_and_read)

        safe_title = (
            "".join(
                c if c.isalnum() or c in " -_" else "_" for c in report.title
            ).strip()[:80]
            or "report"
        )
        ext = _FILE_EXTENSIONS[format]

        return StreamingResponse(
            io.BytesIO(output),
            media_type=_MEDIA_TYPES[format],
            headers={
                "Content-Disposition": f'attachment; filename="{safe_title}.{ext}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Report export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {e!s}") from e


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
