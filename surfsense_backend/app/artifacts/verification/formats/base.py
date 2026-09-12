"""Shared format-adapter contract."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from app.sandbox import SandboxSession

DEFAULT_RENDERED_MIN_CHARS = 20
ReviewKind = Literal["document", "slides"]
VisualSource = Literal["pdf", "image"]


@dataclass(frozen=True, slots=True)
class StructuralCheckResult:
    findings: tuple[str, ...]
    page_count: int | None = None
    notes: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.findings


@dataclass(frozen=True, slots=True)
class SandboxCheckResult:
    structural: StructuralCheckResult
    primary_sha256: str


@dataclass(frozen=True, slots=True)
class FormatAdapter:
    name: str
    suffix: str
    mime_type: str
    convert_to_pdf: bool
    check: Callable[[bytes], StructuralCheckResult]
    rendered_min_chars: int = DEFAULT_RENDERED_MIN_CHARS
    expects_exact_page_count: bool = False
    review_kind: ReviewKind = "document"
    visual_source: VisualSource = "pdf"
    # Orthogonal to convert_to_pdf: PDF keeps convert_to_pdf=False but still
    # needs eyes. Spreadsheets set this False and never enter the visual path.
    requires_visual_review: bool = True
    requires_markdown_binding: bool = False
    markdown_check: Callable[[bytes], StructuralCheckResult] | None = None
    markdown_projection: Callable[[bytes], str] | None = None
    sandbox_check: (
        Callable[[SandboxSession, str], Awaitable[SandboxCheckResult]] | None
    ) = None
