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

from app.services.billable_calls import QuotaInsufficientError
from app.utils.structured_output import invoke_json

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_CALL = 20
VISION_CONCURRENCY = 4
VISION_TIMEOUT_SECONDS = 120


class VisionVerdict(BaseModel):
    clean: bool
    findings: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class VisualReviewResult:
    clean: bool
    findings: tuple[str, ...]
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
    progress: Callable[[int, int], None] | None = None,
) -> VisualReviewResult:
    """Review every page alone and then in consecutive cross-page windows."""
    if not page_images:
        raise ValueError("Artifact verification produced no rendered pages")

    semaphore = asyncio.Semaphore(VISION_CONCURRENCY)
    progress_lock = asyncio.Lock()
    reviewed_pages = 0

    async def invoke(images: tuple[PageImage, ...], *, compare: bool) -> VisionVerdict:
        labels = ", ".join(PurePosixPath(path).name for path, _ in images)
        task = (
            "Compare the attached consecutive pages for cross-page consistency: "
            "fonts, colors, spacing, repeated elements, and unintended page-count "
            "or continuation changes."
            if compare
            else "Inspect the attached page for layout, overflow, clipping, "
            "illegible text, blank content, alignment, and visible factual "
            "inconsistencies."
        )
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"{task}\nFiles: {labels}\n"
                    "Return only JSON with `clean` (boolean) and `findings` "
                    "(an array of concise, actionable strings). `clean` must be "
                    "false when any visible defect exists."
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
                            "url": "data:image/jpeg;base64,"
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

    async def inspect_page(image: PageImage) -> VisionVerdict:
        nonlocal reviewed_pages
        try:
            return await invoke((image,), compare=False)
        finally:
            if progress is not None:
                async with progress_lock:
                    reviewed_pages += 1
                    progress(reviewed_pages, len(page_images))

    calls = [inspect_page(image) for image in page_images]
    if len(page_images) > 1:
        calls.extend(invoke(group, compare=True) for group in _windows(page_images))

    results = await asyncio.gather(*calls, return_exceptions=True)
    quota_failure = next(
        (result for result in results if isinstance(result, QuotaInsufficientError)),
        None,
    )

    findings: list[str] = []
    clean = True
    for result in results:
        if isinstance(result, QuotaInsufficientError):
            continue
        if isinstance(result, BaseException):
            clean = False
            findings.append(f"Visual inspection failed: {result}")
            continue
        if not result.clean or result.findings:
            clean = False
            findings.extend(result.findings or ["Visual inspection found a defect"])
    if not clean:
        return VisualReviewResult(clean=False, findings=tuple(findings))
    if quota_failure is not None:
        return VisualReviewResult(
            clean=False,
            findings=(),
            unavailable_reason=(
                "Visual verification stopped because credit is insufficient: "
                f"{quota_failure}"
            ),
        )
    return VisualReviewResult(clean=clean, findings=tuple(findings))
