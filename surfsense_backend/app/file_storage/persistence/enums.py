"""Kinds of durable files attached to knowledge-base documents."""

from __future__ import annotations

from enum import StrEnum


class DocumentFileKind(StrEnum):
    ORIGINAL = "ORIGINAL"
    REDACTED = "REDACTED"
    FILLED_FORM = "FILLED_FORM"
