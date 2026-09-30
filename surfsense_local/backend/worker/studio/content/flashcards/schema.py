"""The deck reply's shape, enforced as a grammar while the model writes.

Only types and `required`, like the quiz's. The card count stays the
prompt's to ask for and the builder's to cap.
"""

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                },
                "required": ["front", "back"],
            },
        },
    },
    "required": ["title", "cards"],
}
