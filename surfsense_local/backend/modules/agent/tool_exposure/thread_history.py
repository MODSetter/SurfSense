"""What a thread's session tells the next turn's choice of tools.

The last exchange joins the new message in the query, which fixed follow-ups such
as "now the other one"; a tool the thread called stays held until a compaction
drops what it said from the model's view.
"""

from typing import Any

from modules.agent.agent_threads.replies import session_turns
from modules.agent.tool_exposure.held_tools import Asked


def asked_of(
    messages: list[dict[str, Any]], message: str, mentioned: frozenset[str]
) -> Asked:
    turns = session_turns(messages)
    previous = ""
    if turns:
        last = turns[-1]
        said = [
            item.get("text") or ""
            for step in last.steps
            for item in step.get("content") or []
            if item.get("type") == "text"
        ]
        previous = "\n".join([last.user.get("text") or "", *said]).strip()
    return Asked(message, previous, mentioned, frozenset(_used(messages)))


def _used(messages: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()
    for message in messages:
        kind = message.get("type")
        if kind == "compaction" and message.get("status") == "completed":
            used.clear()
        elif kind == "assistant":
            used |= {
                item["name"]
                for item in message.get("content") or []
                if item.get("type") == "tool" and item.get("name")
            }
    return used
