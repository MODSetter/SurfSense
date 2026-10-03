"""The infographic brief's shape, enforced as a grammar while the model writes.

Types and `required` only: the builder trims a label to 60 characters and a
value to 80, and caps the sections, rather than the grammar counting them.
"""

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["label", "value", "detail"],
            },
        },
    },
    "required": ["title", "summary", "sections"],
}
