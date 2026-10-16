"""Where a running Claude Code's tool calls meet the current turn: its gate and its frames.

One Claude Code runs a thread's turns one after another, and its hook and
permission callback are fixed when it starts, so each turn points them here.
The hook answers at once, as it has a timeout; an `ask` is waited on in
`can_use_tool`, which Claude Code calls next.
"""

import asyncio
from typing import Any

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from modules.agent.engines.claude_code.approvals import Approvals
from modules.agent.engines.claude_code.gate import Gate, Verdict
from modules.agent.engines.claude_code.tool_names import step_tool
from modules.agent.opencode_client import Event

REJECTED = "The user rejected this action."


class TurnLink:
    def __init__(self, thread_id: int, approvals: Approvals) -> None:
        self._thread_id = thread_id
        self._approvals = approvals
        self._gate: Gate | None = None
        self._events: asyncio.Queue[Any] | None = None
        self._session_id = ""

    def begin(self, gate: Gate, events: asyncio.Queue[Any], session_id: str) -> None:
        """The turn now running: the rules its calls meet, and where its approvals show."""
        self._gate = gate
        self._events = events
        self._session_id = session_id

    def end(self) -> None:
        """Between turns every call is refused: nothing should be running."""
        self._gate = None
        self._events = None

    def _decide(self, tool: str, tool_input: dict[str, Any]) -> Verdict:
        if self._gate is None:
            return Verdict("deny", "No turn is running.")
        return self._gate.decide(tool, tool_input)

    async def pre_tool_use(
        self, hook_input: dict[str, Any], tool_use_id: str | None, context: Any
    ) -> dict[str, Any]:
        verdict = self._decide(
            hook_input["tool_name"], hook_input.get("tool_input") or {}
        )
        output: dict[str, Any] = {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict.action,
        }
        if verdict.reason:
            output["permissionDecisionReason"] = verdict.reason
        return {"hookSpecificOutput": output}

    async def can_use_tool(
        self, tool: str, tool_input: dict[str, Any], context: Any
    ) -> PermissionResultAllow | PermissionResultDeny:
        verdict = self._decide(tool, tool_input)
        if verdict.action == "allow":
            return PermissionResultAllow()
        if verdict.action == "deny" or self._events is None:
            return PermissionResultDeny(message=verdict.reason or REJECTED)
        call_id = _tool_use_id(context)
        request_id, answer = self._approvals.ask(self._thread_id)
        events = self._events
        await events.put(
            Event(
                type="permission.asked",
                properties={
                    "sessionID": self._session_id,
                    "id": request_id,
                    "permission": step_tool(tool),
                    "patterns": [],
                    "tool": {"callID": call_id},
                },
            )
        )
        reply = await answer
        await events.put(
            Event(
                type="permission.replied",
                properties={
                    "sessionID": self._session_id,
                    "requestID": request_id,
                    "reply": reply,
                },
            )
        )
        if reply == "once":
            return PermissionResultAllow()
        return PermissionResultDeny(message=REJECTED)


def _tool_use_id(context: Any) -> str | None:
    """The call an approval holds back, as the SDK's context names it."""
    if isinstance(context, dict):
        return context.get("tool_use_id")
    return getattr(context, "tool_use_id", None)
