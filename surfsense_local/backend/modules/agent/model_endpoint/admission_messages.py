import json
from typing import Any

from modules.llm.providers.types import Image, Message

# A stand-in for an image part: admission prices images by count, not bytes.
_ANY_IMAGE = Image(mime="image/png", data=b"")


def admission_messages(messages: list[dict[str, Any]]) -> list[Message]:
    """opencode's OpenAI-shaped messages, as admission prices them.

    Text parts and tool calls count as text and image parts count as images,
    so a step is charged for everything it puts in the cache.
    """
    return [_message(message) for message in messages if isinstance(message, dict)]


def _message(message: dict[str, Any]) -> Message:
    content = message.get("content")
    texts: list[str] = []
    images = 0
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                images += 1
            elif isinstance(part.get("text"), str):
                texts.append(part["text"])
    if message.get("tool_calls"):
        texts.append(json.dumps(message["tool_calls"]))
    return Message(
        role=str(message.get("role", "user")),
        content="\n".join(texts),
        images=(_ANY_IMAGE,) * images,
    )
