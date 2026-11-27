"""The image brief's shape, enforced as a grammar while the model writes.

Two strings, both asked for by every tier's prompt: the title names the piece
and the prompt is what the image model paints. Types and `required` only, like
the quiz's.
"""

REPLY = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "prompt": {"type": "string"}},
    "required": ["title", "prompt"],
}
