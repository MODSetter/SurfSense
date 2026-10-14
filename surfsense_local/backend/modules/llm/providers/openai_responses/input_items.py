import base64

from modules.llm.providers.types import Message

# A plan rejects `system` items, and every Responses endpoint ranks a developer
# turn the same way, so a system prompt travels as one.
_ROLES = {"system": "developer"}


def input_items(messages: list[Message]) -> list[dict[str, object]]:
    """A conversation as Responses `input`: plain strings unless a turn has images."""
    return [_item(message) for message in messages]


def _item(message: Message) -> dict[str, object]:
    role = _ROLES.get(message.role, message.role)
    if not message.images:
        return {"role": role, "content": message.content}
    parts: list[dict[str, object]] = [{"type": "input_text", "text": message.content}]
    parts += [
        {
            "type": "input_image",
            "image_url": f"data:{image.mime};base64,"
            + base64.b64encode(image.data).decode(),
        }
        for image in message.images
    ]
    return {"role": role, "content": parts}
