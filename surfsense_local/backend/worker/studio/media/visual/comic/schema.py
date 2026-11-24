"""The plan reply's shape, enforced as a grammar where the endpoint takes one.

Only types and `required`, like the deck's: the page count stays the prompt's
to ask for and the plan's to cut.
"""

_PANEL = {
    "type": "object",
    "properties": {
        "where": {"type": "string"},
        "shows": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["where", "shows", "lines"],
}

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "style": {"type": "string"},
        "characters": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"panels": {"type": "array", "items": _PANEL}},
                "required": ["panels"],
            },
        },
    },
    "required": ["title", "style", "characters", "pages"],
}
