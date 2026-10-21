"""What a chat run is sent: the whole conversation as text for a new run, only
the newest message for a run that already holds the rest."""

import base64
from collections.abc import Sequence
from typing import Any

from modules.llm.providers.types import Message
from modules.llm.subscriptions.claude.run import Prompt


def system_prompt(messages: Sequence[Message]) -> str | None:
    """The first system message, given whole in place of Claude Code's own prompt."""
    if messages and messages[0].role == "system":
        return messages[0].content
    return None


def _turns(messages: Sequence[Message]) -> list[Message]:
    return list(messages[1:] if system_prompt(messages) is not None else messages)


def _newest(message: Message) -> Prompt:
    if not message.images:
        return message.content
    blocks: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image.mime,
                "data": base64.b64encode(image.data).decode(),
            },
        }
        for image in message.images
    ]
    return [*blocks, {"type": "text", "text": message.content}]


def whole_conversation(messages: Sequence[Message]) -> Prompt:
    """Earlier turns tagged by role, then the newest message on its own."""
    turns = _turns(messages)
    *earlier, newest = turns
    if not earlier:
        return _newest(newest)
    told = "\n".join(f"<{t.role}>{t.content}</{t.role}>" for t in earlier)
    preamble = (
        "<conversation>\n"
        f"{told}\n"
        "</conversation>\n"
        "Continue this conversation: answer only the newest message.\n\n"
    )
    newest_prompt = _newest(newest)
    if isinstance(newest_prompt, str):
        return preamble + newest_prompt
    return [{"type": "text", "text": preamble}, *newest_prompt]


def newest_message(messages: Sequence[Message]) -> Prompt:
    return _newest(_turns(messages)[-1])


def continues(held: Sequence[Message], messages: Sequence[Message]) -> bool:
    """Whether `messages` is `held`, the reply to it, and one new user message.

    The reply's text is not compared: the chat stores it after resolving
    citations, so it differs from what the run wrote while meaning the same.
    """
    if len(messages) != len(held) + 2:
        return False
    same_start = all(
        (a.role, a.content, a.images) == (b.role, b.content, b.images)
        for a, b in zip(held, messages, strict=False)
    )
    return (
        same_start
        and messages[len(held)].role == "assistant"
        and messages[-1].role == "user"
    )
