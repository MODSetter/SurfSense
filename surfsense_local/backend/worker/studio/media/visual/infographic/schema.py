"""The infographic brief's shape, enforced as a grammar while the model writes.

Flat, like the quiz's: types, `required` and array bounds only. Every field the
prompts ask for is required; the builder still cuts labels and values to what
a drawn panel can hold.
"""

# The frontier prompt leaves the count to the material, so the ceiling is kept
# here: past this a drawn panel stops being readable.
SECTIONS = 8

_TEXT = {"type": "string"}

REPLY = {
    "type": "object",
    "properties": {
        "title": _TEXT,
        "summary": _TEXT,
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": _TEXT, "value": _TEXT, "detail": _TEXT},
                "required": ["label", "value", "detail"],
            },
            "minItems": 1,
            "maxItems": SECTIONS,
        },
    },
    "required": ["title", "summary", "sections"],
}
