"""The quiz reply's shape, enforced as a grammar while the model writes.

Flat and plain on purpose: only types, `required` and array bounds, which
llama.cpp's json-schema-to-grammar turns into a bounded repetition at b11050.
That an answer is one of its options cannot be said here; the builder still
checks it.
"""

# The prompts ask for exactly this many; the builder drops any other count.
OPTIONS = 4

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": OPTIONS,
                        "maxItems": OPTIONS,
                    },
                    "answer": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["question", "options", "answer", "explanation"],
            },
        },
    },
    "required": ["title", "questions"],
}
