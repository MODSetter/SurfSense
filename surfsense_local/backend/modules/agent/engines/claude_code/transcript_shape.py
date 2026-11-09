"""A Claude Code transcript as opencode's messages, so the thread reads both engines' turns alike.

A user entry with words opens a turn, SurfSense's notes before it as synthetic
messages; each API message of the reply is an assistant message, as opencode's
steps are, and a tool result completes the call it answers. Claude Code's own
entries are left out.
"""

from datetime import datetime
from typing import Any

from modules.agent.engines.claude_code.tool_names import step_input, step_tool
from modules.agent.engines.claude_code.tool_result import result_text

# What Claude Code writes as a user message that the user never sent.
_NOT_THE_USERS = ("isCompactSummary", "isMeta", "isSidechain")
_INTERRUPTED = "[Request interrupted"


def opencode_messages(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    calls: dict[str, dict[str, Any]] = {}
    opener: str | None = None
    for entry in entries:
        if any(entry.get(flag) for flag in _NOT_THE_USERS):
            continue
        at = _ms(entry.get("timestamp"))
        content = (entry.get("message") or {}).get("content")
        if entry.get("type") == "user":
            if isinstance(content, list) and _answers_calls(content):
                _complete(content, calls)
                continue
            said = _user_texts(content)
            if said is None:
                continue
            notes, words = said
            opener = entry["uuid"]
            messages += [
                {
                    "id": f"{opener}:note:{n}",
                    "type": "synthetic",
                    "text": note,
                    "time": {"created": at},
                }
                for n, note in enumerate(notes)
            ]
            messages.append(
                {"id": opener, "type": "user", "text": words, "time": {"created": at}}
            )
        elif entry.get("type") == "assistant" and opener is not None:
            message_id = entry["message"]["id"]
            message = by_id.get(message_id)
            if message is None:
                message = {
                    "id": message_id,
                    "type": "assistant",
                    "content": [],
                    "time": {"created": at},
                }
                by_id[message_id] = message
                messages.append(message)
            message["time"]["completed"] = at
            for block in content or []:
                item = _assistant_item(block)
                if item is None:
                    continue
                message["content"].append(item)
                if item["type"] == "tool":
                    calls[item["id"]] = item
    return messages


def _answers_calls(content: list[dict[str, Any]]) -> bool:
    return any(block.get("type") == "tool_result" for block in content)


def _complete(content: list[dict[str, Any]], calls: dict[str, dict[str, Any]]) -> None:
    for block in content:
        item = calls.get(block.get("tool_use_id", ""))
        if item is None:
            continue
        text = result_text(block.get("content"))
        given = item["state"]["input"]
        if block.get("is_error"):
            error = {"type": "tool.execution", "message": text}
            item["state"] = {"status": "error", "input": given, "error": error}
        else:
            answered = [{"type": "text", "text": text}]
            item["state"] = {"status": "completed", "input": given, "content": answered}


def _user_texts(content: Any) -> tuple[list[str], str] | None:
    """SurfSense's notes, which go as blocks of their own, and the user's words last."""
    if isinstance(content, str):
        texts = [content]
    else:
        texts = [b["text"] for b in content or [] if b.get("type") == "text"]
    if not texts or texts[-1].startswith(_INTERRUPTED):
        return None
    *notes, words = texts
    return notes, words


def _assistant_item(block: dict[str, Any]) -> dict[str, Any] | None:
    kind = block.get("type")
    if kind == "text":
        return {"type": "text", "text": block["text"]}
    if kind == "thinking" and block.get("thinking"):
        return {"type": "reasoning", "text": block["thinking"]}
    if kind == "tool_use":
        return {
            "type": "tool",
            "id": block["id"],
            "name": step_tool(block["name"]),
            # Running until its result is read: an unanswered call was cut short.
            "state": {
                "status": "running",
                "input": step_input(block["name"], block["input"]),
            },
        }
    return None


def _ms(timestamp: str | None) -> int | None:
    if timestamp is None:
        return None
    return int(datetime.fromisoformat(timestamp).timestamp() * 1000)
