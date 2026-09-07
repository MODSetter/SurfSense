import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_SLUG = re.compile(r"[^a-z0-9]+")


def parse_json(raw: str) -> dict[str, Any]:
    """Pull the JSON object a model returned, tolerating fences and stray prose.

    Local models wrap JSON in ```json fences or add a sentence around it, so the
    outermost braces are isolated before parsing rather than trusting the model
    to answer with nothing else.
    """
    text = raw.strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"model did not return valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data


def slug(title: str, fallback: str) -> str:
    """A safe file stem from a title, for the download filename."""
    cleaned = _SLUG.sub("-", title.lower()).strip("-")
    return cleaned[:60] or fallback


def as_list(value: Any) -> list[Any]:
    """A list whatever the model gave, so a missing or scalar field is empty."""
    return value if isinstance(value, list) else []


def as_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""
