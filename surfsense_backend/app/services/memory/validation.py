"""Validation helpers for markdown-backed memory."""

from __future__ import annotations

from typing import Literal

from app.services.memory.document import (
    extract_headings,
    has_explicit_heading,
    nonstandard_bullets,
    parse_memory_document,
)

MEMORY_SOFT_LIMIT = 18_000
MEMORY_HARD_LIMIT = 25_000

_FORBIDDEN_TEAM_HEADINGS = {
    "preferences",
    "instructions",
    "personal notes",
    "personal instructions",
}


def has_markdown_heading(content: str) -> bool:
    return has_explicit_heading(content)


def strip_preamble_to_first_heading(content: str) -> str:
    """Drop model preamble before the first ``##`` heading, if one exists."""
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip():
            return "\n".join(lines[index:]).strip()
    return content.strip()


def validate_memory_size(content: str) -> dict[str, str] | None:
    length = len(content)
    if length > MEMORY_HARD_LIMIT:
        return {
            "status": "error",
            "message": (
                f"Memory exceeds {MEMORY_HARD_LIMIT:,} character limit "
                f"({length:,} chars). Consolidate by merging related items, "
                "removing outdated entries, and shortening descriptions."
            ),
        }
    return None


def validate_heading_sanity(content: str) -> dict[str, str] | None:
    """Block long prose blobs without headings unless they are legacy bullets."""
    stripped = content.strip()
    if not stripped:
        return None
    if has_markdown_heading(stripped):
        return None
    if len(stripped) <= 40:
        return None
    if parse_memory_document(stripped).sections:
        return None
    return {
        "status": "error",
        "message": "Memory must be markdown with at least one ## heading.",
    }


def validate_memory_scope(
    content: str,
    scope: Literal["user", "team"],
    *,
    old_memory: str | None = None,
) -> tuple[dict[str, str] | None, list[str]]:
    """Reject new personal headings in team memory, grandfather existing ones."""
    if scope != "team":
        return None, []

    old_forbidden = extract_headings(old_memory) & _FORBIDDEN_TEAM_HEADINGS
    new_forbidden = extract_headings(content) & _FORBIDDEN_TEAM_HEADINGS
    introduced = sorted(new_forbidden - old_forbidden)
    grandfathered = sorted(new_forbidden & old_forbidden)

    warnings: list[str] = []
    if grandfathered:
        warnings.append(
            "Team memory contains legacy personal headings: "
            + ", ".join(grandfathered)
            + ". Please consolidate them into team-safe headings."
        )
    if introduced:
        return (
            {
                "status": "error",
                "message": (
                    "Team memory cannot introduce personal headings: "
                    + ", ".join(introduced)
                    + ". Use team-safe headings instead."
                ),
            },
            warnings,
        )
    return None, warnings


def validate_bullet_format(content: str) -> list[str]:
    return nonstandard_bullets(content)


def validate_diff(old_memory: str | None, new_memory: str) -> list[str]:
    if not old_memory:
        return []

    warnings: list[str] = []
    old_headings = extract_headings(old_memory)
    new_headings = extract_headings(new_memory)
    dropped = old_headings - new_headings
    if dropped:
        names = ", ".join(sorted(dropped))
        warnings.append(
            f"Sections removed: {names}. If unintentional, restore them from the memory document."
        )

    old_len = len(old_memory)
    new_len = len(new_memory)
    if old_len > 0 and new_len < old_len * 0.4:
        warnings.append(
            f"Memory shrank significantly ({old_len:,} -> {new_len:,} chars). Possible data loss."
        )
    return warnings


def soft_limit_warning(content: str) -> str | None:
    length = len(content)
    if length > MEMORY_SOFT_LIMIT:
        return (
            f"Memory is at {length:,}/{MEMORY_HARD_LIMIT:,} characters. "
            "Consolidate by merging related items and removing less important entries."
        )
    return None
