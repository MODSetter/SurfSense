"""Visual artifact review over sandbox-rendered JPEG pages."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.artifacts.verification.formats.base import ReviewKind
from app.services.billable_calls import QuotaInsufficientError
from app.utils.structured_output import invoke_json

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_CALL = 20
VISION_CONCURRENCY = 4
VISION_TIMEOUT_SECONDS = 120

REVIEW_FRAMINGS: dict[ReviewKind, str] = {
    "document": (
        "Review these consecutive pages together as one flowing document. "
        "Text continuing naturally across a page boundary and unused space at the "
        "end of the final page are not defects. Check for clipping, overlap, "
        "unreadable text, blank or corrupt pages, missing content, and cross-page "
        "layout inconsistency."
    ),
    "slides": (
        "Review these consecutive presentation slides together. Each slide is "
        "self-contained: text or a list unintentionally continuing onto another "
        "slide is a defect, while unused space is not. Check for clipping, overlap, "
        "unreadable text, blank or corrupt slides, missing content, and consistency "
        "of template, type scale, and palette across slides."
    ),
    "infographic": (
        "Review this infographic against the supplied factual contract. Block "
        "missing or misspelled critical facts, changed numbers, contradictions, "
        "clipping, unreadable text, duplicated or omitted sections, placeholder "
        "copy, watermarks, unsafe content, a merely decorative scene instead of "
        "an infographic, or failure to visibly follow the requested style."
    ),
}
VERDICT_INSTRUCTIONS = (
    "Return only JSON with `blocking_findings` and `warnings`, both arrays of "
    "concise, actionable strings. A blocking finding must make the artifact "
    "unusable or incomplete: clipped/overlapping or unreadable content, a "
    "blank/corrupt page or slide, or missing content. Put minor contrast, "
    "whitespace, alignment, and aesthetic suggestions in warnings; do not block "
    "the artifact for them."
)


class VisionVerdict(BaseModel):
    blocking_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VisualReviewResult:
    clean: bool
    findings: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    unavailable_reason: str | None = None


PageImage = tuple[str, bytes]


def _windows(images: tuple[PageImage, ...]) -> list[tuple[PageImage, ...]]:
    groups: list[tuple[PageImage, ...]] = []
    start = 0
    while start < len(images):
        groups.append(images[start : start + MAX_IMAGES_PER_CALL])
        if start + MAX_IMAGES_PER_CALL >= len(images):
            break
        # Retain one boundary page so adjacent pages are always compared.
        start += MAX_IMAGES_PER_CALL - 1
    return groups


async def review_pages(
    llm: Any,
    page_images: tuple[PageImage, ...],
    *,
    review_kind: ReviewKind = "document",
    reference_text: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> VisualReviewResult:
    """Review consecutive rendered windows using format-appropriate framing."""
    if not page_images:
        raise ValueError("Artifact verification produced no rendered pages")

    semaphore = asyncio.Semaphore(VISION_CONCURRENCY)
    progress_lock = asyncio.Lock()
    reviewed_pages = 0

    async def invoke(images: tuple[PageImage, ...]) -> VisionVerdict:
        labels = ", ".join(PurePosixPath(path).name for path, _ in images)
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"{REVIEW_FRAMINGS[review_kind]}\n"
                    f"Files: {labels}\n"
                    + (
                        f"Factual and generation contract:\n{reference_text[:20_000]}\n"
                        if reference_text
                        else ""
                    )
                    + VERDICT_INSTRUCTIONS
                ),
            }
        ]
        for path, data in images:
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"Image {path} exceeds the {MAX_IMAGE_BYTES}-byte limit"
                )
            content.extend(
                (
                    {"type": "text", "text": f"Filename: {path}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/png;base64,"
                                if data.startswith(b"\x89PNG\r\n\x1a\n")
                                else "data:image/jpeg;base64,"
                            )
                            + base64.b64encode(data).decode("ascii")
                        },
                    },
                )
            )
        async with semaphore:
            return await asyncio.wait_for(
                invoke_json(llm, [HumanMessage(content=content)], VisionVerdict),
                timeout=VISION_TIMEOUT_SECONDS,
            )

    async def inspect_window(images: tuple[PageImage, ...]) -> VisionVerdict:
        nonlocal reviewed_pages
        try:
            return await invoke(images)
        finally:
            if progress is not None:
                async with progress_lock:
                    reviewed_pages += len(images) - (1 if reviewed_pages else 0)
                    reviewed_pages = min(reviewed_pages, len(page_images))
                    progress(reviewed_pages, len(page_images))

    calls = [inspect_window(group) for group in _windows(page_images)]

    results = await asyncio.gather(*calls, return_exceptions=True)
    quota_failure = next(
        (result for result in results if isinstance(result, QuotaInsufficientError)),
        None,
    )

    findings: list[str] = []
    warnings: list[str] = []
    for result in results:
        if isinstance(result, QuotaInsufficientError):
            continue
        if isinstance(result, BaseException):
            findings.append(f"Visual inspection failed: {result}")
            continue
        findings.extend(result.blocking_findings)
        warnings.extend(result.warnings)
    if findings:
        return VisualReviewResult(
            clean=False,
            findings=tuple(findings),
            warnings=tuple(warnings),
        )
    if quota_failure is not None:
        return VisualReviewResult(
            clean=False,
            findings=(),
            warnings=tuple(warnings),
            unavailable_reason=(
                "Visual verification stopped because credit is insufficient: "
                f"{quota_failure}"
            ),
        )
    return VisualReviewResult(
        clean=True,
        findings=(),
        warnings=tuple(warnings),
    )
