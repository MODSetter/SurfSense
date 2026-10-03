"""The image writer's reply, enforced as a grammar while the model writes.

Both fields required: without a prompt there is nothing to paint, and the job
fails after the writer's time is spent.
"""

REPLY = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "prompt": {"type": "string"},
    },
    "required": ["title", "prompt"],
}
