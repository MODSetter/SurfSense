"""Shared format-adapter contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StructuralCheckResult:
    findings: tuple[str, ...]
    page_count: int | None = None
    notes: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.findings


@dataclass(frozen=True, slots=True)
class FormatAdapter:
    name: str
    suffix: str
    convert_to_pdf: bool
    check: Callable[[bytes], StructuralCheckResult]
