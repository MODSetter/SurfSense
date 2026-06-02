"""DocumentFile kinds: the original upload plus future derived artifacts."""

from __future__ import annotations

from enum import StrEnum


class DocumentFileKind(StrEnum):
    ORIGINAL = "ORIGINAL"
    REDACTED = "REDACTED"
    FILLED_FORM = "FILLED_FORM"
