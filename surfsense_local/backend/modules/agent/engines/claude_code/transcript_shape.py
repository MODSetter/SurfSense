"""A Claude Code transcript as opencode's messages, so the thread reads both engines' turns alike.

A user entry with words opens a turn; each API message of the reply is an
assistant message, as opencode's steps are, and a tool result completes the
call it answers. Claude Code's own entries are left out.
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
            parts = _user_parts(content)
            if not parts:
                continue
            opener = entry["uuid"]
            messages.append(
                {
                    "info": {"id": opener, "role": "user", "time": {"created": at}},
                    "parts": parts,
                }
            )
        elif entry.get("type") == "assistant" and opener is not None:
            message_id = entry["message"]["id"]
            message = by_id.get(message_id)
            if message is None:
                message = {
                    "info": {
                        "id": message_id,
                        "role": "assistant",
                        "parentID": opener,
                        "time": {"created": at},
                    },
                    "parts": [],
                }
                by_id[message_id] = message
                messages.append(message)
            message["info"]["time"]["completed"] = at
            for block in content or []:
                part = _assistant_part(block, f"{message_id}:{len(message['parts'])}")
                if part is None:
                    continue
                part["messageID"] = message_id
                message["parts"].append(part)
                if part["type"] == "tool":
                    calls[part["callID"]] = part
    return messages


def _answers_calls(content: list[dict[str, Any]]) -> bool:
    return any(block.get("type") == "tool_result" for block in content)


def _complete(content: list[dict[str, Any]], calls: dict[str, dict[str, Any]]) -> None:
    for block in content:
        part = calls.get(block.get("tool_use_id", ""))
        if part is None:
            continue
        text = result_text(block.get("content"))
        given = part["state"]["input"]
        if block.get("is_error"):
            part["state"] = {"status": "error", "input": given, "error": text}
        else:
            part["state"] = {"status": "completed", "input": given, "output": text}


def _user_parts(content: Any) -> list[dict[str, Any]]:
    """The user's words last, after SurfSense's notes, which go as blocks of their own."""
    if isinstance(content, str):
        texts = [content]
    else:
        texts = [b["text"] for b in content or [] if b.get("type") == "text"]
    if not texts or texts[-1].startswith(_INTERRUPTED):
        return []
    *notes, words = texts
    return [
        *({"type": "text", "text": note, "synthetic": True} for note in notes),
        {"type": "text", "text": words},
    ]


def _assistant_part(block: dict[str, Any], part_id: str) -> dict[str, Any] | None:
    kind = block.get("type")
    if kind == "text":
        return {"id": part_id, "type": "text", "text": block["text"]}
    if kind == "thinking" and block.get("thinking"):
        return {"id": part_id, "type": "reasoning", "text": block["thinking"]}
    if kind == "tool_use":
        return {
            "id": block["id"],
            "type": "tool",
            "callID": block["id"],
            "tool": step_tool(block["name"]),
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
