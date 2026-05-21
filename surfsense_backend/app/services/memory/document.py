"""Memory-specific markdown document model and canonical renderer.

This intentionally parses only SurfSense memory's small markdown contract:
``##`` sections with dated bullet items. Unknown lines are preserved so user
edits are not lost, while legacy marker bullets are normalized on render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

DEFAULT_LEGACY_SECTION = "Memory"
LEGACY_MARKERS = frozenset({"fact", "pref", "instr"})


@dataclass(frozen=True)
class MemoryBullet:
    entry_date: date
    text: str


@dataclass(frozen=True)
class MemoryRawLine:
    text: str


MemoryLine = MemoryBullet | MemoryRawLine


@dataclass(frozen=True)
class MemorySection:
    heading: str
    lines: list[MemoryLine] = field(default_factory=list)
    explicit_heading: bool = True


@dataclass(frozen=True)
class MemoryDocument:
    sections: list[MemorySection] = field(default_factory=list)

    @property
    def has_explicit_heading(self) -> bool:
        return any(section.explicit_heading for section in self.sections)


def is_section_heading(line: str) -> bool:
    return line.startswith("## ") and bool(line[3:].strip())


def heading_text(line: str) -> str:
    return line[3:].strip()


def normalize_heading(heading: str) -> str:
    chars: list[str] = []
    previous_was_space = True
    for char in heading.strip().lower():
        if char.isalnum():
            chars.append(char)
            previous_was_space = False
        elif not previous_was_space:
            chars.append(" ")
            previous_was_space = True
    return "".join(chars).strip()


def parse_bullet_line(line: str) -> MemoryBullet | None:
    stripped = line.strip()
    if not stripped.startswith("- "):
        return None

    body = stripped[2:]
    parsed = _parse_canonical_bullet(body)
    if parsed is not None:
        return parsed
    return _parse_legacy_bullet(body)


def _parse_canonical_bullet(body: str) -> MemoryBullet | None:
    if len(body) < 13 or body[10:12] != ": ":
        return None
    try:
        entry_date = date.fromisoformat(body[:10])
    except ValueError:
        return None
    text = body[12:].strip()
    if not text:
        return None
    return MemoryBullet(entry_date=entry_date, text=text)


def _parse_legacy_bullet(body: str) -> MemoryBullet | None:
    if len(body) < 20 or not body.startswith("("):
        return None
    if len(body) < 14 or body[11:14] != ") [":
        return None
    try:
        entry_date = date.fromisoformat(body[1:11])
    except ValueError:
        return None

    marker_end = body.find("] ", 14)
    if marker_end == -1:
        return None
    marker = body[14:marker_end]
    if marker not in LEGACY_MARKERS:
        return None

    text = body[marker_end + 2 :].strip()
    if not text:
        return None
    return MemoryBullet(entry_date=entry_date, text=text)


def parse_memory_document(content: str | None) -> MemoryDocument:
    if not content:
        return MemoryDocument()

    sections: list[MemorySection] = []
    current_heading: str | None = None
    current_explicit = True
    current_lines: list[MemoryLine] = []

    def flush_current() -> None:
        nonlocal current_heading, current_explicit, current_lines
        if current_heading is None:
            return
        sections.append(
            MemorySection(
                heading=current_heading,
                lines=current_lines,
                explicit_heading=current_explicit,
            )
        )
        current_heading = None
        current_explicit = True
        current_lines = []

    for raw_line in content.strip().splitlines():
        line = raw_line.rstrip()
        if is_section_heading(line):
            flush_current()
            current_heading = heading_text(line)
            current_explicit = True
            current_lines = []
            continue

        bullet = parse_bullet_line(line)
        if current_heading is None:
            if bullet is None:
                continue
            current_heading = DEFAULT_LEGACY_SECTION
            current_explicit = False
            current_lines = [bullet]
            continue

        current_lines.append(bullet if bullet is not None else MemoryRawLine(text=line))

    flush_current()
    return MemoryDocument(sections=sections)


def render_memory_document(document: MemoryDocument) -> str:
    rendered_sections: list[str] = []
    for section in document.sections:
        section_lines = [f"## {section.heading}"]
        for line in section.lines:
            if isinstance(line, MemoryBullet):
                section_lines.append(f"- {line.entry_date.isoformat()}: {line.text}")
            else:
                section_lines.append(line.text)
        rendered_sections.append("\n".join(section_lines).strip())
    return "\n\n".join(section for section in rendered_sections if section).strip()


def extract_headings(memory: str | None) -> set[str]:
    document = parse_memory_document(memory)
    return {
        normalize_heading(section.heading)
        for section in document.sections
        if section.explicit_heading
    }


def has_explicit_heading(content: str) -> bool:
    return parse_memory_document(content).has_explicit_heading


def nonstandard_bullets(content: str) -> list[str]:
    warnings: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if parse_bullet_line(stripped) is not None:
            continue
        short = stripped[:80] + ("..." if len(stripped) > 80 else "")
        warnings.append(f"Non-standard memory bullet: {short}")
    return warnings
