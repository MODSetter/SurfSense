"""``<specialists>`` section — live ``task`` roster for this workspace."""

from __future__ import annotations


def build_specialists_section(
    specialist_lines: list[tuple[str, str]] | None,
) -> str:
    if specialist_lines is None:
        return ""
    if not specialist_lines:
        return (
            "\n<specialists>\n"
            "No specialists are available for `task` in this workspace.\n"
            "</specialists>\n"
        )
    bullets = "\n".join(f"- **{name}** — {desc}" for name, desc in specialist_lines)
    return f"\n<specialists>\n{bullets}\n</specialists>\n"
