"""The page reply's shape, enforced as a grammar while the model writes.

Plain strings only: the builder escapes every value into a fixed template, so
the schema asks for text and the page stays unable to carry markup. The
section count stays the prompt's to ask for and the builder's to cap.
"""

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["heading", "paragraphs"],
            },
        },
    },
    "required": ["title", "sections"],
}
