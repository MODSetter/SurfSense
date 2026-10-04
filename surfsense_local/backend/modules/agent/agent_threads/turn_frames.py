"""opencode's events for one turn, turned into the frames the chat stream speaks.

The chat's frames carry over (`accepted`, `delta`, `reasoning`, `error`), and
the agent adds three: `agent-step` for a tool call's progress, and
`permission-request` and `permission-replied` for an approval.
"""

from typing import Any

from modules.agent.agent_threads.compaction import is_summary
from modules.agent.agent_threads.replies import PARAGRAPH, iso_from_ms, reply_id
from modules.agent.agent_threads.steps import step_of
from modules.agent.opencode_client import Event

Frame = dict[str, Any]
_STREAMED = {"text": "delta", "reasoning": "reasoning"}
# What opencode reports when a request is too long, then compacts and carries on from.
_OVERFLOW = "ContextOverflowError"
_TOO_LONG = "The conversation is too long to continue here; start a new thread."


class TurnFrames:
    """Reads one session's events in order and says what the thread should show."""

    def __init__(self, session_id: str) -> None:
        self._session = session_id
        self._roles: dict[str, str] = {}
        self._kinds: dict[str, str] = {}
        self._streamed: dict[str, int] = {}
        self._answered: set[str] = set()
        self._step_status: dict[str, str] = {}
        self._thought: set[str] = set()
        self._failed = False
        self.user_message_id: str | None = None
        self.finished = False

    def frames(self, event: Event) -> list[Frame]:
        """What this event adds to the thread; nothing for another session's."""
        if event.properties.get("sessionID") != self._session:
            return []
        read = {
            "message.updated": self._message,
            "message.part.updated": self._part,
            "message.part.delta": self._delta,
            "permission.asked": self._asked,
            "permission.replied": self._replied,
            "session.error": self._error,
            "session.idle": self._idle,
        }.get(event.type)
        return read(event.properties) if read else []

    def _message(self, properties: dict[str, Any]) -> list[Frame]:
        """Learn whose message it is; the turn's own user message opens the reply."""
        info = properties["info"]
        # A compaction's summary is opencode's note to itself, never the reply.
        if is_summary(info):
            self._roles[info["id"]] = "summary"
            # One that failed ends the turn; when it was too long, only the summary says so.
            return self._failure(_reason(info["error"])) if info.get("error") else []
        self._roles[info["id"]] = info["role"]
        if info["role"] != "user" or self.user_message_id is not None:
            return []
        self.user_message_id = info["id"]
        return [
            {
                "type": "accepted",
                "user_message_id": info["id"],
                "assistant_message_id": reply_id(info["id"]),
                "user_created_at": iso_from_ms(info.get("time", {}).get("created")),
            }
        ]

    def _part(self, properties: dict[str, Any]) -> list[Frame]:
        """A step's progress, or text a delta has not carried yet."""
        part = properties["part"]
        if self._roles.get(part.get("messageID")) != "assistant":
            return []
        if part.get("type") == "tool":
            return self._step(part)
        if part.get("type") not in _STREAMED:
            return []
        self._kinds[part["id"]] = part["type"]
        frames = self._catch_up(part["id"], part.get("text") or "")
        if part["type"] == "reasoning":
            frames += self._thinking_ended(part)
        return frames

    def _delta(self, properties: dict[str, Any]) -> list[Frame]:
        """Streamed text, for a part already announced as answer or reasoning."""
        kind = self._kinds.get(properties.get("partID", ""))
        if properties.get("field") != "text" or kind not in _STREAMED:
            return []
        self._streamed[properties["partID"]] = self._streamed.get(
            properties["partID"], 0
        ) + len(properties["delta"])
        return self._shown(properties["partID"], properties["delta"])

    def _catch_up(self, part_id: str, text: str) -> list[Frame]:
        """The end of a part's text that no delta streamed, so nothing is lost."""
        streamed = self._streamed.get(part_id, 0)
        if len(text) <= streamed:
            return []
        self._streamed[part_id] = len(text)
        return self._shown(part_id, text[streamed:])

    def _shown(self, part_id: str, text: str) -> list[Frame]:
        """A part's next text; a later answer part opens a new paragraph.

        opencode starts a new part after each tool call, and its text begins with
        no break of its own.
        """
        kind = self._kinds[part_id]
        if kind == "text" and text.strip() and part_id not in self._answered:
            if self._answered:
                text = PARAGRAPH + text
            self._answered.add(part_id)
        return [{"type": _STREAMED[kind], "text": text}]

    def _thinking_ended(self, part: dict[str, Any]) -> list[Frame]:
        """How long a reasoning part took, once, when it ends."""
        time = part.get("time") or {}
        if part["id"] in self._thought or time.get("end") is None:
            return []
        self._thought.add(part["id"])
        return [
            {
                "type": "reasoning-end",
                "duration_ms": time["end"] - time.get("start", time["end"]),
            }
        ]

    def _step(self, part: dict[str, Any]) -> list[Frame]:
        """A tool call, each time its status moves."""
        status = (part.get("state") or {}).get("status")
        if self._step_status.get(part["id"]) == status:
            return []
        self._step_status[part["id"]] = status
        return [{"type": "agent-step", **step_of(part)}]

    def _asked(self, properties: dict[str, Any]) -> list[Frame]:
        """The agent wants to run something the user must allow first."""
        return [
            {
                "type": "permission-request",
                "id": properties["id"],
                "permission": properties["permission"],
                "patterns": properties.get("patterns") or [],
                "command": (properties.get("metadata") or {}).get("command"),
            }
        ]

    def _replied(self, properties: dict[str, Any]) -> list[Frame]:
        """An approval answered, from this window or another."""
        return [
            {
                "type": "permission-replied",
                "id": properties["requestID"],
                "reply": properties["reply"],
            }
        ]

    def _error(self, properties: dict[str, Any]) -> list[Frame]:
        """The turn failed; opencode says why in the error's data."""
        error = properties.get("error") or {}
        if error.get("name") == _OVERFLOW:
            return []  # opencode compacts and carries on (compaction.auto is on)
        return self._failure(_reason(error))

    def _failure(self, message: str) -> list[Frame]:
        """The turn's one error frame: opencode can report a failure twice."""
        if self._failed:
            return []
        self._failed = True
        return [
            {
                "type": "error",
                "kind": "unknown",
                "message": message,
                "provider": "opencode",
            }
        ]

    def _idle(self, properties: dict[str, Any]) -> list[Frame]:
        """The session is done, once the turn has begun."""
        if self.user_message_id is not None:
            self.finished = True
        return []


def _reason(error: dict[str, Any]) -> str:
    """What to tell the user about an error opencode reports."""
    if error.get("name") == _OVERFLOW:
        return _TOO_LONG
    return (
        (error.get("data") or {}).get("message")
        or error.get("name")
        or "The agent stopped with an error."
    )
