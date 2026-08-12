"""Orchestrate structural, rendered, and visual artifact verification."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import dispatch_custom_event

from app.config import config as app_config
from app.sandbox import SandboxSession

from .formats.pdf import check_pdf
from .formats.registry import get_format_adapter
from .receipt import (
    RECEIPT_PATH,
    VerificationReceipt,
    sha256_bytes,
    write_receipt,
)
from .render import prepare_pdf, rasterize_pdf
from .vision import review_pages

logger = logging.getLogger(__name__)

ARTIFACT_MAX_VERIFY_PAGES = 40


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verified: bool
    findings: tuple[str, ...]
    notes: tuple[str, ...] = ()
    preview_path: str | None = None
    page_count: int | None = None
    unavailable_reason: str | None = None


def _progress(phase: str, message: str, **details: int) -> None:
    try:
        dispatch_custom_event(
            "verification_progress",
            {"phase": phase, "message": message, **details},
        )
    except Exception:
        # Unit tests and non-graph callers have no callback context.
        logger.debug("verification progress dispatch skipped", exc_info=True)


async def verify_artifact(
    session: SandboxSession,
    primary_path: str,
    *,
    workspace_id: int,
    vision_llm: Any | None,
    secret_key: str | None = None,
) -> VerificationResult:
    """Verify one artifact and issue a signed receipt only when it may be saved."""
    signing_key = secret_key if secret_key is not None else app_config.SECRET_KEY
    if not signing_key:
        raise ValueError("SECRET_KEY is required for artifact verification")
    # Invalidate any earlier pass before starting this attempt. A failed rerun
    # must not leave a still-usable receipt for the same bytes.
    await session.write_file(RECEIPT_PATH, b"")
    try:
        return await _verify_artifact(
            session,
            primary_path,
            workspace_id=workspace_id,
            vision_llm=vision_llm,
            signing_key=signing_key,
        )
    except Exception as exc:
        logger.warning("Artifact verification failed: %s", exc, exc_info=True)
        return VerificationResult(
            verified=False,
            findings=(f"Artifact verification failed: {exc}",),
        )


async def _verify_artifact(
    session: SandboxSession,
    primary_path: str,
    *,
    workspace_id: int,
    vision_llm: Any | None,
    signing_key: str,
) -> VerificationResult:
    adapter = get_format_adapter(primary_path)
    _progress("checking", "Checking document structure")
    primary_data = await session.read_file(primary_path)
    if len(primary_data) > app_config.ARTIFACT_MAX_FILE_BYTES:
        return VerificationResult(
            verified=False,
            findings=(
                f"Artifact is {len(primary_data)} bytes; limit is "
                f"{app_config.ARTIFACT_MAX_FILE_BYTES} bytes",
            ),
        )

    structural = adapter.check(primary_data)
    if not structural.clean:
        return VerificationResult(
            verified=False,
            findings=structural.findings,
            notes=structural.notes,
            page_count=structural.page_count,
        )
    if (
        structural.page_count is not None
        and structural.page_count > ARTIFACT_MAX_VERIFY_PAGES
    ):
        return VerificationResult(
            verified=False,
            findings=(
                f"Document has {structural.page_count} pages; verification supports "
                f"at most {ARTIFACT_MAX_VERIFY_PAGES}",
            ),
            notes=structural.notes,
            page_count=structural.page_count,
        )

    if not adapter.requires_visual_review:
        receipt = VerificationReceipt(
            workspace_id=workspace_id,
            session_id=session.session_id,
            format=adapter.name,
            primary_path=primary_path,
            primary_sha256=sha256_bytes(primary_data),
            preview_path=None,
            preview_sha256=None,
            page_count=None,
            visual="not_required",
            unavailable_reason=None,
            issued_at=int(time.time()),
        )
        await write_receipt(session, receipt, signing_key)
        _progress("complete", "Document verification complete")
        return VerificationResult(
            verified=True,
            findings=(),
            notes=structural.notes,
            preview_path=None,
            page_count=structural.page_count,
        )

    _progress(
        "converting" if adapter.convert_to_pdf else "preparing",
        "Converting document to PDF"
        if adapter.convert_to_pdf
        else "Preparing PDF for review",
    )
    prepared = await prepare_pdf(
        session,
        primary_path,
        primary_data,
        convert_to_pdf=adapter.convert_to_pdf,
    )
    preview_data = (
        await session.read_file(prepared.pdf_path)
        if adapter.convert_to_pdf
        else primary_data
    )
    rendered_pdf = (
        check_pdf(
            preview_data,
            expected_pages=structural.page_count
            if adapter.expects_exact_page_count
            else None,
            min_chars=adapter.rendered_min_chars,
        )
        if adapter.convert_to_pdf
        else structural
    )
    if not rendered_pdf.clean:
        return VerificationResult(
            verified=False,
            findings=rendered_pdf.findings,
            notes=structural.notes,
            preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
            page_count=rendered_pdf.page_count,
        )

    page_count = rendered_pdf.page_count
    if page_count is None or page_count > ARTIFACT_MAX_VERIFY_PAGES:
        return VerificationResult(
            verified=False,
            findings=(
                f"Document has {page_count or 0} pages; verification supports at most "
                f"{ARTIFACT_MAX_VERIFY_PAGES}",
            ),
            notes=structural.notes,
            preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
            page_count=page_count,
        )

    _progress("rendering", f"Rendering {page_count} page(s)", total=page_count)
    page_paths = await rasterize_pdf(session, prepared)
    if len(page_paths) != page_count:
        return VerificationResult(
            verified=False,
            findings=(
                f"Rendered {len(page_paths)} page image(s) for a {page_count}-page document",
            ),
            notes=structural.notes,
            preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
            page_count=page_count,
        )
    if await session.read_file(prepared.source_path) != primary_data:
        return VerificationResult(
            verified=False,
            findings=("The verification source changed while it was being rendered",),
            notes=structural.notes,
            preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
            page_count=page_count,
        )
    if await session.read_file(prepared.pdf_path) != preview_data:
        return VerificationResult(
            verified=False,
            findings=("The rendered preview changed during verification",),
            notes=structural.notes,
            preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
            page_count=page_count,
        )
    page_images = []
    for path in page_paths:
        page_images.append((path, await session.read_file(path)))

    notes = list(structural.notes)
    unavailable_reason = None
    if vision_llm is None:
        unavailable_reason = "No vision-capable model is configured for this workspace"
    else:
        _progress("reviewing", f"Reviewing {page_count} page(s)", total=page_count)
        visual = await review_pages(
            vision_llm,
            tuple(page_images),
            review_kind=adapter.review_kind,
            progress=lambda current, total: _progress(
                "reviewing",
                f"Inspecting page {current} of {total}",
                current=current,
                total=total,
            ),
        )
        notes.extend(visual.warnings)
        if visual.unavailable_reason:
            unavailable_reason = visual.unavailable_reason
        elif not visual.clean:
            return VerificationResult(
                verified=False,
                findings=visual.findings,
                notes=tuple(notes),
                preview_path=prepared.pdf_path if adapter.convert_to_pdf else None,
                page_count=page_count,
            )

    preview_path = prepared.pdf_path if adapter.convert_to_pdf else None
    receipt = VerificationReceipt(
        workspace_id=workspace_id,
        session_id=session.session_id,
        format=adapter.name,
        primary_path=primary_path,
        primary_sha256=sha256_bytes(primary_data),
        preview_path=preview_path,
        preview_sha256=sha256_bytes(preview_data) if preview_path else None,
        page_count=page_count,
        visual="unavailable" if unavailable_reason else "clean",
        unavailable_reason=unavailable_reason,
        issued_at=int(time.time()),
    )
    await write_receipt(
        session,
        receipt,
        signing_key,
    )
    _progress("complete", "Document verification complete")
    return VerificationResult(
        verified=True,
        findings=(),
        notes=tuple(notes),
        preview_path=preview_path,
        page_count=page_count,
        unavailable_reason=unavailable_reason,
    )
