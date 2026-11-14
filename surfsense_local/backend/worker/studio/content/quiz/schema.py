"""The quiz reply's shape, enforced as a grammar while the model writes.

Flat and plain on purpose: only types, `required` and array bounds, which
llama.cpp's json-schema-to-grammar turns into a bounded repetition at b11050.
The answer is a field of its own rather than a copy of one option: small
models answered "A" or "a. sunlight", and each such question was lost.
"""

# The viewer shows this many options; the builder shuffles the answer in.
OPTIONS = 4
DISTRACTORS = OPTIONS - 1


def reply(*, at_least: int, at_most: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "correct": {"type": "string"},
                        "distractors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": DISTRACTORS,
                            "maxItems": DISTRACTORS,
                        },
                        "explanation": {"type": "string"},
                    },
                    "required": ["question", "correct", "distractors", "explanation"],
                },
                "minItems": at_least,
                "maxItems": at_most,
            },
        },
        "required": ["title", "questions"],
    }
