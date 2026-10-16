"""Claude Code's messages as opencode's events, so one turn reader serves both engines.

Each API message is an assistant message, as opencode starts one per step; text
and thinking stream from the raw events, a tool call's input comes with its
finished block and its result with the next user message.
"""

import time
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from modules.agent.engines.claude_code.tool_names import step_input, step_tool
from modules.agent.engines.claude_code.tool_result import result_text
from modules.agent.opencode_client import Event

_KINDS = {"text": "text", "thinking": "reasoning"}


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class OpencodeShape:
    """One Claude Code session's turn, read in order."""

    def __init__(self, session_id: str) -> None:
        self._session = session_id
        self._message = ""
        self._announced: set[str] = set()
        # Text and reasoning parts by stream position, and in the order they began,
        # so a finished block finds the part its deltas went to.
        self._by_index: dict[tuple[str, int], dict[str, Any]] = {}
        self._begun: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._finished: dict[tuple[str, str], int] = {}
        self._tools: dict[str, dict[str, Any]] = {}

    def user(self, message_id: str, created_ms: int) -> list[Event]:
        """The turn's own user message, which opens the reply."""
        info = {"id": message_id, "role": "user", "time": {"created": created_ms}}
        return [self._event("message.updated", info=info)]

    def read(self, message: Any) -> list[Event]:
        if getattr(message, "parent_tool_use_id", None):
            return []  # a subagent's, and SurfSense gives none
        if isinstance(message, StreamEvent):
            return self._stream(message.event)
        if isinstance(message, AssistantMessage):
            return self._assistant(message)
        if isinstance(message, UserMessage):
            return self._results(message)
        if isinstance(message, ResultMessage):
            return [self._event("session.idle")]
        return []

    def _stream(self, event: dict[str, Any]) -> list[Event]:
        kind = event.get("type")
        if kind == "message_start":
            return self._announce(event["message"]["id"])
        index = event.get("index", -1)
        if kind == "content_block_start":
            return self._block_started(index, event["content_block"])
        part = self._by_index.get((self._message, index))
        if part is None:
            return []
        if kind == "content_block_delta":
            delta = event["delta"]
            text = delta.get("text") or delta.get("thinking")
            if delta.get("type") not in {"text_delta", "thinking_delta"} or not text:
                return []
            part["text"] += text
            return [
                self._event(
                    "message.part.delta", partID=part["id"], field="text", delta=text
                )
            ]
        if kind == "content_block_stop" and part["type"] == "reasoning":
            part["time"]["end"] = _now_ms()
            return [self._part(part)]
        return []

    def _block_started(self, index: int, block: dict[str, Any]) -> list[Event]:
        if block.get("type") == "tool_use":
            return [self._tool(block["id"], block["name"], {}, "pending")]
        kind = _KINDS.get(block.get("type", ""))
        if kind is None:
            return []
        part = self._new_part(kind, f"{self._message}:{index}")
        self._by_index[(self._message, index)] = part
        return [self._part(part)]

    def _assistant(self, message: AssistantMessage) -> list[Event]:
        events = self._announce(message.message_id or message.uuid or self._message)
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                tool_input = step_input(block.name, block.input)
                events.append(self._tool(block.id, block.name, tool_input, "running"))
            elif isinstance(block, TextBlock):
                events += self._whole("text", block.text)
            elif isinstance(block, ThinkingBlock):
                events += self._whole("reasoning", block.thinking)
        return events

    def _whole(self, kind: str, text: str) -> list[Event]:
        """A finished block: the part its deltas went to, given its whole text, or a new part."""
        key = (self._message, kind)
        seen = self._finished.get(key, 0)
        self._finished[key] = seen + 1
        begun = self._begun.get(key, [])
        if seen < len(begun):
            part = begun[seen]
        else:
            part = self._new_part(kind, f"{self._message}:{kind}:{seen}")
            if kind == "reasoning":
                part["time"]["end"] = part["time"]["start"]
        part["text"] = text
        return [self._part(part)]

    def _results(self, message: UserMessage) -> list[Event]:
        if isinstance(message.content, str):
            return []
        events = []
        for block in message.content:
            if not isinstance(block, ToolResultBlock):
                continue
            part = self._tools.get(block.tool_use_id)
            if part is None:
                continue
            text = result_text(block.content)
            state = part["state"]
            if block.is_error:
                part["state"] = {
                    "status": "error",
                    "input": state["input"],
                    "error": text,
                }
            else:
                part["state"] = {
                    "status": "completed",
                    "input": state["input"],
                    "output": text,
                }
            events.append(self._part(part))
        return events

    def _tool(
        self, call_id: str, name: str, tool_input: dict[str, Any], status: str
    ) -> Event:
        part = self._tools.setdefault(
            call_id,
            {
                "id": call_id,
                "messageID": self._message,
                "type": "tool",
                "callID": call_id,
                "tool": step_tool(name),
            },
        )
        part["state"] = {"status": status, "input": tool_input}
        return self._part(part)

    def _announce(self, message_id: str) -> list[Event]:
        self._message = message_id
        if message_id in self._announced:
            return []
        self._announced.add(message_id)
        return [
            self._event("message.updated", info={"id": message_id, "role": "assistant"})
        ]

    def _new_part(self, kind: str, part_id: str) -> dict[str, Any]:
        part: dict[str, Any] = {
            "id": part_id,
            "messageID": self._message,
            "type": kind,
            "text": "",
        }
        if kind == "reasoning":
            part["time"] = {"start": _now_ms()}
        self._begun.setdefault((self._message, kind), []).append(part)
        return part

    def _part(self, part: dict[str, Any]) -> Event:
        return self._event("message.part.updated", part=dict(part))

    def _event(self, kind: str, **properties: Any) -> Event:
        return Event(type=kind, properties={"sessionID": self._session, **properties})
