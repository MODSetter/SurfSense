"""Claude Code's messages as opencode's events, so one turn reader serves both engines.

Each API message is a step, an assistant message, as opencode stores one per
step; text and thinking stream from the raw events, keyed by their block's
place in the message as opencode keys its items. A tool call's input comes with
its finished block and its result with the next user message.
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
# Past any block's place in a message: blocks seen only once they finished.
_UNSTREAMED = 1000


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class OpencodeShape:
    """One Claude Code session's turn, read in order."""

    def __init__(self, session_id: str) -> None:
        self._session = session_id
        self._message = ""
        # Text and reasoning items by their block's place, and in the order they
        # began, so a finished block finds the item its deltas went to.
        self._by_index: dict[tuple[str, int], tuple[int, dict[str, Any]]] = {}
        self._begun: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
        self._finished: dict[tuple[str, str], int] = {}
        self._tools: dict[str, dict[str, Any]] = {}
        # The turn as opencode stores one, so its reply is stated from what streamed.
        self._messages: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}

    def user(self, message_id: str, created_ms: int) -> list[Event]:
        """The turn's own user message, which opens the reply."""
        self._messages.append(
            {
                "id": message_id,
                "type": "user",
                "text": "",
                "time": {"created": created_ms},
            }
        )
        return [
            self._event(
                "session.inbox.enqueued",
                created_ms,
                inboxID=message_id,
                item={"type": "user"},
            )
        ]

    def messages(self) -> list[dict[str, Any]]:
        """The turn read so far, as opencode's messages."""
        return self._messages

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
            if self._message in self._by_id:
                self._by_id[self._message]["time"]["completed"] = _now_ms()
            self._messages.append(
                {"id": f"{self._session}:idle", "type": "idle", "outcome": "succeeded"}
            )
            return [self._event("session.execution.succeeded")]
        return []

    def _stream(self, event: dict[str, Any]) -> list[Event]:
        kind = event.get("type")
        if kind == "message_start":
            return self._announce(event["message"]["id"])
        index = event.get("index", -1)
        if kind == "content_block_start":
            return self._block_started(index, event["content_block"])
        found = self._by_index.get((self._message, index))
        if found is None:
            return []
        ordinal, item = found
        if kind == "content_block_delta":
            delta = event["delta"]
            text = delta.get("text") or delta.get("thinking")
            if delta.get("type") not in {"text_delta", "thinking_delta"} or not text:
                return []
            item["text"] += text
            return [self._item_event(item, "delta", ordinal, delta=text)]
        if kind == "content_block_stop" and item["type"] == "reasoning":
            return [self._item_event(item, "ended", ordinal, text=item["text"])]
        return []

    def _block_started(self, index: int, block: dict[str, Any]) -> list[Event]:
        if block.get("type") == "tool_use":
            item = self._tool(block["id"], block["name"])
            item["state"] = {"status": "streaming", "input": ""}
            return [
                self._event(
                    "session.tool.input.started",
                    assistantMessageID=self._message,
                    id=block["id"],
                    name=item["name"],
                )
            ]
        kind = _KINDS.get(block.get("type", ""))
        if kind is None:
            return []
        item = self._new_item(kind, index)
        self._by_index[(self._message, index)] = (index, item)
        return [self._item_event(item, "started", index)]

    def _assistant(self, message: AssistantMessage) -> list[Event]:
        events = self._announce(message.message_id or message.uuid or self._message)
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                if block.id not in self._tools:
                    # Not streamed: named here, as opencode names a call before its input.
                    named = {"type": "tool_use", "id": block.id, "name": block.name}
                    events += self._block_started(-1, named)
                item = self._tool(block.id, block.name)
                tool_input = step_input(block.name, block.input)
                item["state"] = {"status": "running", "input": tool_input}
                events.append(
                    self._event(
                        "session.tool.called",
                        assistantMessageID=self._message,
                        id=block.id,
                        input=tool_input,
                    )
                )
            elif isinstance(block, TextBlock):
                events += self._whole("text", block.text)
            elif isinstance(block, ThinkingBlock):
                events += self._whole("reasoning", block.thinking)
        return events

    def _whole(self, kind: str, text: str) -> list[Event]:
        """A finished block: the item its deltas went to, given its whole text, or a new item."""
        key = (self._message, kind)
        seen = self._finished.get(key, 0)
        self._finished[key] = seen + 1
        begun = self._begun.get(key, [])
        if seen < len(begun):
            ordinal, item = begun[seen]
        else:
            ordinal = _UNSTREAMED + seen
            item = self._new_item(kind, ordinal)
        item["text"] = text
        return [self._item_event(item, "ended", ordinal, text=text)]

    def _results(self, message: UserMessage) -> list[Event]:
        if isinstance(message.content, str):
            return []
        events = []
        for block in message.content:
            if not isinstance(block, ToolResultBlock):
                continue
            item = self._tools.get(block.tool_use_id)
            if item is None:
                continue
            text = result_text(block.content)
            given = item["state"].get("input")
            given = given if isinstance(given, dict) else {}
            content = [{"type": "text", "text": text}]
            if block.is_error:
                error = {"type": "tool.execution", "message": text}
                item["state"] = {"status": "error", "input": given, "error": error}
                events.append(
                    self._tool_event("session.tool.failed", item, error=error)
                )
            else:
                item["state"] = {
                    "status": "completed",
                    "input": given,
                    "content": content,
                }
                events.append(
                    self._tool_event("session.tool.success", item, content=content)
                )
        return events

    def _tool(self, call_id: str, name: str) -> dict[str, Any]:
        item = self._tools.get(call_id)
        if item is None:
            item = {"type": "tool", "id": call_id, "name": step_tool(name), "state": {}}
            self._tools[call_id] = item
            self._add(item)
        return item

    def _announce(self, message_id: str) -> list[Event]:
        self._message = message_id
        if message_id in self._by_id:
            return []
        message = {
            "id": message_id,
            "type": "assistant",
            "content": [],
            "time": {"created": _now_ms()},
        }
        self._by_id[message_id] = message
        self._messages.append(message)
        return [self._event("session.step.started", assistantMessageID=message_id)]

    def _new_item(self, kind: str, ordinal: int) -> dict[str, Any]:
        item: dict[str, Any] = {"type": kind, "text": ""}
        self._begun.setdefault((self._message, kind), []).append((ordinal, item))
        self._add(item)
        return item

    def _add(self, item: dict[str, Any]) -> None:
        message = self._by_id.get(self._message)
        if message is not None:
            message["content"].append(item)
            message["time"]["completed"] = _now_ms()

    def _item_event(
        self, item: dict[str, Any], stage: str, ordinal: int, **data: Any
    ) -> Event:
        return self._event(
            f"session.{item['type']}.{stage}",
            assistantMessageID=self._message,
            ordinal=ordinal,
            **data,
        )

    def _tool_event(self, kind: str, item: dict[str, Any], **data: Any) -> Event:
        return self._event(
            kind, assistantMessageID=self._message, id=item["id"], **data
        )

    def _event(self, kind: str, created: int | None = None, **data: Any) -> Event:
        return Event(
            type=kind,
            created=created or _now_ms(),
            data={"sessionID": self._session, **data},
        )
