"""A pulled thing as one markdown source: a title, its facts, then its sections."""

from collections.abc import Iterable

# A fact or a section with nothing in it is left out.
Fact = tuple[str, object]
Section = tuple[str, str | None]


def source_markdown(
    title: str, facts: Iterable[Fact], sections: Iterable[Section]
) -> str:
    parts = [f"# {title}"]
    listed = [
        f"- **{label}:** {_shown(value)}" for label, value in facts if _present(value)
    ]
    if listed:
        parts.append("\n".join(listed))
    parts += [
        f"## {name}\n\n{body.strip()}"
        for name, body in sections
        if body and body.strip()
    ]
    return "\n\n".join(parts)


def _present(value: object) -> bool:
    return value is not None and value != "" and value != []


def _shown(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
