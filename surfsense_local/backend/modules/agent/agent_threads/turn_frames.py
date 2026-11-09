"""opencode's events for one turn, turned into the frames the chat stream speaks.

The chat's frames carry over (`accepted`, `delta`, `reasoning`, `error`), and
the agent adds three: `agent-step` for a tool call's progress, and
`permission-request` and `permission-replied` for an approval.
"""

from typing import Any

from modules.agent.agent_threads.error_kind import error_kind
from modules.agent.agent_threads.error_reason import error_reason
from modules.agent.agent_threads.replies import PARAGRAPH, iso_from_ms, reply_id
from modules.agent.agent_threads.steps import step_of
from modules.agent.opencode_client import Event

Frame = dict[str, Any]
_STREAMED = {"text": "delta", "reasoning": "reasoning"}
# How a turn ends; a declined approval ends it as interrupted, with no idle message.
ENDED = frozenset(
    {
        "session.execution.succeeded",
        "session.execution.failed",
        "session.execution.interrupted",
    }
)


class TurnFrames:
    """Reads one session's events in order and says what the thread should show."""

    def __init__(self, session_id: str) -> None:
        self._session = session_id
        # Text and reasoning by (step, ordinal), as opencode keys them.
        self._kinds: dict[str, str] = {}
        self._streamed: dict[str, int] = {}
        self._answered: set[str] = set()
        self._held: dict[str, str] = {}
        self._thinking: dict[str, int] = {}
        self._thought: set[str] = set()
        # Each tool call as opencode stores it, built from its events.
        self._tools: dict[str, dict[str, Any]] = {}
        self._failed = False
        self.user_message_id: str | None = None
        self.finished = False

    def frames(self, event: Event) -> list[Frame]:
        """What this event adds to the thread; nothing for another session's."""
        data = event.data
        if data.get("sessionID") != self._session:
            return []
        if event.type in ENDED:
            return self._ended(event)
        if self.user_message_id is None:
            return self._opened(event)
        read = {
            "session.text.started": self._started,
            "session.text.delta": self._delta,
            "session.text.ended": self._whole,
            "session.reasoning.started": self._started,
            "session.reasoning.delta": self._delta,
            "session.reasoning.ended": self._whole,
            "session.tool.input.started": self._tool_named,
            "session.tool.called": self._tool_called,
            "session.tool.success": self._tool_answered,
            "session.tool.failed": self._tool_answered,
            "permission.asked": self._asked,
            "permission.replied": self._replied,
        }.get(event.type)
        return read(event) if read else []

    def _opened(self, event: Event) -> list[Frame]:
        """The turn's own user message, queued, opens the reply; SurfSense's notes come before it."""
        item = event.data.get("item") or {}
        if event.type != "session.inbox.enqueued" or item.get("type") != "user":
            return []
        self.user_message_id = event.data["inboxID"]
        return [
            {
                "type": "accepted",
                "user_message_id": self.user_message_id,
                "assistant_message_id": reply_id(self.user_message_id),
                "user_created_at": iso_from_ms(event.created),
            }
        ]

    def _started(self, event: Event) -> list[Frame]:
        key = _key(event.data)
        self._kinds[key] = event.type.split(".")[1]
        if self._kinds[key] == "reasoning":
            self._thinking[key] = event.created or 0
        return []

    def _delta(self, event: Event) -> list[Frame]:
        """Streamed text, for an item already announced as answer or reasoning."""
        key = _key(event.data)
        if key not in self._kinds:
            return []
        self._streamed[key] = self._streamed.get(key, 0) + len(event.data["delta"])
        return self._shown(key, event.data["delta"])

    def _whole(self, event: Event) -> list[Frame]:
        """An item's whole text: the end of it no delta streamed, so nothing is lost."""
        key = _key(event.data)
        self._kinds.setdefault(key, event.type.split(".")[1])
        text = event.data.get("text") or ""
        frames: list[Frame] = []
        streamed = self._streamed.get(key, 0)
        if len(text) > streamed:
            self._streamed[key] = len(text)
            frames = self._shown(key, text[streamed:])
        if self._kinds[key] == "reasoning" and key not in self._thought:
            self._thought.add(key)
            began = self._thinking.get(key)
            ended = event.created
            frames.append(
                {
                    "type": "reasoning-end",
                    "duration_ms": (ended - began) if began and ended else 0,
                }
            )
        return frames

    def _shown(self, key: str, text: str) -> list[Frame]:
        """An item's next text; a later answer item opens a new paragraph.

        opencode starts a new item after each tool call, and models lead or end
        items with breaks, or send items of breaks only. An item's breaks are
        held until text follows them, and its leading ones dropped, so items
        join with one blank line, as the stored reply's do.
        """
        kind = self._kinds[key]
        if kind != "text":
            return [{"type": _STREAMED[kind], "text": text}]
        text = self._held.pop(key, "") + text
        body = text.rstrip()
        if not body:
            self._held[key] = text
            return []
        if "\n" in text[len(body) :]:
            self._held[key] = text[len(body) :]
            text = body
        if key not in self._answered:
            text = text.lstrip()
            if self._answered:
                text = PARAGRAPH + text
            self._answered.add(key)
        return [{"type": "delta", "text": text}]

    def _tool_named(self, event: Event) -> list[Frame]:
        """A call the model began writing."""
        item = self._tool(event.data["id"])
        item["name"] = event.data["name"]
        item["state"] = {"status": "streaming", "input": ""}
        return self._step(item)

    def _tool_called(self, event: Event) -> list[Frame]:
        """A call with its whole input, about to run or be asked about."""
        item = self._tool(event.data["id"])
        item["state"] = {"status": "running", "input": event.data.get("input") or {}}
        return self._step(item)

    def _tool_answered(self, event: Event) -> list[Frame]:
        item = self._tool(event.data["id"])
        given = (item.get("state") or {}).get("input")
        state: dict[str, Any] = {
            "status": "completed" if event.type == "session.tool.success" else "error",
            "input": given if isinstance(given, dict) else {},
        }
        for field in ("content", "metadata", "error"):
            if event.data.get(field) is not None:
                state[field] = event.data[field]
        item["state"] = state
        return self._step(item)

    def _tool(self, call_id: str) -> dict[str, Any]:
        return self._tools.setdefault(call_id, {"type": "tool", "id": call_id})

    def _step(self, item: dict[str, Any]) -> list[Frame]:
        return [{"type": "agent-step", **step_of(item)}]

    def _asked(self, event: Event) -> list[Frame]:
        """The agent wants to run something the user must allow first."""
        data = event.data
        metadata = data.get("metadata") or {}
        return [
            {
                "type": "permission-request",
                "id": data["id"],
                "permission": data.get("action"),
                "patterns": data.get("resources") or [],
                "command": (metadata.get("input") or {}).get("command"),
                # The tool call it holds back, so the thread asks on that step.
                "call_id": (data.get("source") or {}).get("id"),
            }
        ]

    def _replied(self, event: Event) -> list[Frame]:
        """An approval answered, from this window or another."""
        return [
            {
                "type": "permission-replied",
                "id": event.data["requestID"],
                "reply": event.data["reply"],
            }
        ]

    def _ended(self, event: Event) -> list[Frame]:
        """The turn is done once it has begun; a failure says why."""
        if self.user_message_id is None:
            return []
        self.finished = True
        if event.type != "session.execution.failed" or self._failed:
            return []
        self._failed = True
        error = event.data.get("error") or {}
        return [
            {
                "type": "error",
                "kind": error_kind(error),
                "message": error_reason(error),
                "provider": "opencode",
            }
        ]


def _key(data: dict[str, Any]) -> str:
    return f"{data['assistantMessageID']}:{data['ordinal']}"
