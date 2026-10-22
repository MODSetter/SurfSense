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


def bullets(lines: Iterable[str]) -> str | None:
    """None for no lines, so the section is left out."""
    kept = [f"- {line}" for line in lines if line]
    return "\n".join(kept) or None


def count(number: object, noun: str) -> str:
    """`312 likes`, or nothing when the plugin gave no count."""
    return f" ({_shown(number)} {noun})" if _present(number) else ""


def rating(score: float | None, reviews: int | None) -> str | None:
    if score is None:
        return None
    if not reviews:
        return f"{score:g} out of 5"
    return f"{score:g} out of 5, from {reviews:,} reviews"


def price(amount: dict | None) -> str | None:
    """`{"value": 29.99, "currency": "$"}` as the plugins give a price."""
    if not amount or amount.get("value") is None:
        return None
    return f"{amount['value']} {amount.get('currency') or ''}".strip()


def review(author: str | None, about: list[str], *said: str | None) -> str:
    """`**Ana** (5 stars, 2 Sep): Accurate. Matches.`; nothing when it says nothing."""
    text = ". ".join(part.strip().rstrip(".") for part in said if part and part.strip())
    if not text:
        return ""
    when = f" ({', '.join(about)})" if about else ""
    return f"**{author or 'Someone'}**{when}: {text}."


def about(*parts: str | None) -> str | None:
    """A list row's second line: `Sea School · 00:03:00`; None with nothing to say."""
    return " · ".join(part for part in parts if part) or None


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
