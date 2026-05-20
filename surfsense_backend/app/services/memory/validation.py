"""Validation helpers for markdown-backed memory."""

from __future__ import annotations

import re
from typing import Literal

MEMORY_SOFT_LIMIT = 18_000
MEMORY_HARD_LIMIT = 25_000

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_HEADING_LINE_RE = re.compile(r"^##\s+\S+", re.MULTILINE)
_HEADING_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_LEGACY_BULLET_RE = re.compile(
    r"^-\s+\(\d{4}-\d{2}-\d{2}\)\s+\[(fact|pref|instr)\]\s+.+$"
)
_NEW_BULLET_RE = re.compile(r"^-\s+\d{4}-\d{2}-\d{2}:\s+.+$")

_FORBIDDEN_TEAM_HEADINGS = {
    "preferences",
    "instructions",
    "personal notes",
    "personal instructions",
}


def has_markdown_heading(content: str) -> bool:
    return bool(_HEADING_LINE_RE.search(content))


def strip_preamble_to_first_heading(content: str) -> str:
    """Drop model preamble before the first ``##`` heading, if one exists."""
    match = _HEADING_LINE_RE.search(content)
    if not match:
        return content.strip()
    return content[match.start() :].strip()


def extract_headings(memory: str | None) -> set[str]:
    if not memory:
        return set()
    return {_normalize_heading(h) for h in _SECTION_HEADING_RE.findall(memory)}


def _normalize_heading(heading: str) -> str:
    return _HEADING_NORMALIZE_RE.sub(" ", heading.strip().lower()).strip()


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
    if any(_LEGACY_BULLET_RE.match(line.strip()) for line in stripped.splitlines()):
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
    warnings: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if _NEW_BULLET_RE.match(stripped) or _LEGACY_BULLET_RE.match(stripped):
            continue
        short = stripped[:80] + ("..." if len(stripped) > 80 else "")
        warnings.append(f"Non-standard memory bullet: {short}")
    return warnings


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
            f"Sections removed: {names}. If unintentional, restore from the settings page."
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
