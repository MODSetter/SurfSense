"""The deck reply's shape, enforced as a grammar while the model writes.

Only types, `required` and array bounds, like the quiz's. The bounds hold a
small model to its count and stop one that repeats from filling the window.
"""


def reply(*, at_least: int, at_most: int) -> dict:
    return {
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
                "minItems": at_least,
                "maxItems": at_most,
            },
        },
        "required": ["title", "cards"],
    }
