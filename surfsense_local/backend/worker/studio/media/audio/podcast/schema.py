"""The podcast's two reply shapes, enforced as a grammar while the model writes.

Flat, like the quiz's: types, `required`, array bounds and the cast's slots.
"""

# Twice the 2-5 talking points every outline prompt asks a segment for.
TALKING_POINTS = 10
# The outline prompt asks for "about" its segment count; only a model that
# repeats writes twice as many. Unbounded, nothing stops it: the outline call
# has no token cap.
SEGMENTS_PER_ASKED = 2

_TEXT = {"type": "string"}


def outline(*, segments: int) -> dict:
    """The plan, holding at most twice the segments the prompt asked for."""
    segment = {
        "type": "object",
        "properties": {
            "title": _TEXT,
            "talking_points": {
                "type": "array",
                "items": _TEXT,
                "maxItems": TALKING_POINTS,
            },
            "target_words": {"type": "integer"},
        },
        "required": ["title", "talking_points", "target_words"],
    }
    return {
        "type": "object",
        "properties": {
            "title": _TEXT,
            "segments": {
                "type": "array",
                "items": segment,
                "minItems": 1,
                "maxItems": segments * SEGMENTS_PER_ASKED,
            },
        },
        "required": ["title", "segments"],
    }


def draft(*, speakers: int) -> dict:
    """A segment's lines, each attributed to a slot in the cast.

    The parser also takes a speaker's name or the slot as text, which only an
    unconstrained reply sends; under the grammar a line for nobody in the cast
    cannot be written. The turns have no bound of their own: the segment's
    token cap already stops a reply that loops.
    """
    return {
        "type": "object",
        "properties": {
            "turns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {
                            "type": "integer",
                            "enum": list(range(1, speakers + 1)),
                        },
                        "text": _TEXT,
                    },
                    "required": ["speaker", "text"],
                },
                "minItems": 1,
            },
        },
        "required": ["turns"],
    }
