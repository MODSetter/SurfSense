"""Provider-neutral message formatting helpers."""

from __future__ import annotations

MAX_GATEWAY_TEXT_CHARS = 4096


def split_text_message(
    text: str,
    *,
    max_chars: int = MAX_GATEWAY_TEXT_CHARS,
) -> list[str]:
    """Split outbound text at readable boundaries without exceeding platform caps."""
    if not text:
        return [""]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        candidate = remaining[:max_chars]
        boundary = max(
            candidate.rfind("\n\n"),
            candidate.rfind("\n"),
            candidate.rfind(". "),
            candidate.rfind(" "),
        )
        if boundary <= max(200, max_chars // 2):
            boundary = max_chars
        split_at = boundary + (2 if candidate[boundary : boundary + 2] == ". " else 1)
        chunk = remaining[:split_at].rstrip()
        chunks.append(chunk or remaining[:max_chars])
        remaining = remaining[split_at:].lstrip()

    return chunks
