"""Telegram formatting helpers."""

from __future__ import annotations

import re

from app.gateway.base.formatting import split_text_message

MARKDOWN_V2_RESERVED = r"_*[]()~`>#+-=|{}.!"
MAX_TELEGRAM_MESSAGE_UNITS = 4096

_RESERVED_RE = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}\.!])")


def escape_markdown_v2(text: str) -> str:
    """Escape all Telegram MarkdownV2 reserved characters."""
    return _RESERVED_RE.sub(r"\\\1", text)


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _split_at_boundary(text: str, max_units: int) -> tuple[str, str]:
    if _utf16_len(text) <= max_units:
        return text, ""

    # Build a hard upper bound by code point, then walk back to natural
    # boundaries.  Telegram's limit is UTF-16 code units, so verify candidates.
    end = min(len(text), max_units)
    while end > 0 and _utf16_len(text[:end]) > max_units:
        end -= 1

    candidate = text[:end]
    boundary = max(candidate.rfind("\n\n"), candidate.rfind(". "), candidate.rfind("\n"))
    if boundary > max(200, end // 2):
        end = boundary + (2 if candidate[boundary : boundary + 2] in {"\n\n", ". "} else 1)

    return text[:end], text[end:]


def chunk_message(
    text: str,
    *,
    max_units: int = MAX_TELEGRAM_MESSAGE_UNITS,
) -> list[str]:
    """Split a Telegram message at paragraph/sentence boundaries."""
    if max_units == MAX_TELEGRAM_MESSAGE_UNITS:
        if not text:
            return [""]

        chunks: list[str] = []
        remaining = text
        while remaining:
            chunk, remaining = _split_at_boundary(remaining, max_units)
            chunks.append(chunk)
        return chunks
    return split_text_message(text, max_chars=max_units)

