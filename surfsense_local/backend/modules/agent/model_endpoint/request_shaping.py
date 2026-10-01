"""opencode's request, in the shape local chat templates accept and with nothing a document can smuggle in."""

import re
from typing import Any

_INSTRUCTIONS = {"system", "developer"}
# Roles whose text can carry a source's words: what the user pastes, what a tool read.
_UNTRUSTED = {"user", "tool"}

# Control tokens llama-server would read as the template's own, so a document
# could close its turn and speak as the system. A zero-width space between the
# first two characters leaves the text readable and the token unmatched.
_CONTROL_TOKENS = (
    re.compile(r"<(\|[^|<>\s]{1,64}\|>)"),
    re.compile(r"<(/?(?:tool_call|tool_response|think|start_of_turn|end_of_turn)>)"),
    re.compile(r"\[(/?(?:INST|TOOL_CALLS|TOOL_RESULTS|AVAILABLE_TOOLS)\])"),
)
_UNSPLIT = {"<": "<​", "[": "[​"}


def shaped_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One system message first, no empty assistant turns, control tokens defused."""
    instructions = "\n\n".join(
        text for m in messages if m.get("role") in _INSTRUCTIONS if (text := _text(m))
    )
    rest = [
        _defused(m)
        for m in messages
        if m.get("role") not in _INSTRUCTIONS and not _empty_assistant(m)
    ]
    return (
        [{"role": "system", "content": instructions}, *rest] if instructions else rest
    )


def _text(message: dict[str, Any]) -> str:
    """A message's text, whether it came as a string or as text parts."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _empty_assistant(message: dict[str, Any]) -> bool:
    """A turn a template would continue instead of answering: no text and no call."""
    return (
        message.get("role") == "assistant"
        and not message.get("tool_calls")
        and not _text(message).strip()
    )


def _defused(message: dict[str, Any]) -> dict[str, Any]:
    """The message with control tokens broken in any text a source could have written."""
    if message.get("role") not in _UNTRUSTED:
        return message
    content = message.get("content")
    if isinstance(content, str):
        return {**message, "content": _defuse(content)}
    if isinstance(content, list):
        parts = [
            {**part, "text": _defuse(part["text"])}
            if isinstance(part, dict) and isinstance(part.get("text"), str)
            else part
            for part in content
        ]
        return {**message, "content": parts}
    return message


def _defuse(text: str) -> str:
    """Every control token in `text`, split by a zero-width space after its opener."""
    for pattern in _CONTROL_TOKENS:
        text = pattern.sub(
            lambda match: _UNSPLIT[match.group(0)[0]] + match.group(1), text
        )
    return text
