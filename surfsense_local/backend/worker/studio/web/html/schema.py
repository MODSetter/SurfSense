"""The simple page's reply shape, enforced as a grammar while the model writes.

Unconstrained, Qwen3 0.6B broke 4 pages in 9 and Qwen3 4B 3 in 9: a quote left
unescaped, a bracket too many, a section repeated until the window ran out.
Flat, like the quiz's: types, `required` and array bounds only. Each tier is
held to the fields its prompt asks for.
"""

from modules.llm.profile import Tier

SECTIONS = 10
# Twice what any prompt asks under one heading; only a model that repeats meets it.
PARAGRAPHS = 4
POINTS = 12

_TEXT = {"type": "string"}


def _texts(at_most: int) -> dict:
    return {"type": "array", "items": _TEXT, "maxItems": at_most}


def reply(tier: Tier) -> dict:
    compact = tier is Tier.COMPACT
    section: dict = {
        "type": "object",
        "properties": {"heading": _TEXT, "paragraphs": _texts(PARAGRAPHS)},
        "required": ["heading", "paragraphs"] if compact else ["heading"],
    }
    properties: dict = {"title": _TEXT}
    if not compact:
        section["properties"]["points"] = _texts(POINTS)
        properties["summary"] = _TEXT
    properties["sections"] = {
        "type": "array",
        "items": section,
        "minItems": 1,
        "maxItems": SECTIONS,
    }
    return {
        "type": "object",
        "properties": properties,
        "required": ["title", "sections"],
    }
