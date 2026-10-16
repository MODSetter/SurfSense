"""A Claude Code agent turn played from a script, as Claude Code 2.1.301 plays one.

Each tool call meets the run's own PreToolUse hook and, on an `ask`, its
can_use_tool, as Claude Code calls them; each line is mirrored to the run's
session store, as the SDK mirrors the transcript.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    PermissionResultAllow,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from tests.claude_run_stand_in import ScriptedRun


@dataclass(frozen=True)
class Say:
    text: str


@dataclass(frozen=True)
class Call:
    """A tool call and what the tool returns if the gate lets it run."""

    tool: str
    input: dict[str, Any]
    result: str = "done"


@dataclass(frozen=True)
class Fail:
    """Claude Code reports an error on an assistant message, as when signed out."""

    error: str


@dataclass(frozen=True)
class Hang:
    """Writes, then waits until the turn is interrupted."""

    text: str


Step = Say | Call | Fail | Hang


class ScriptedAgentRun(ScriptedRun):
    def __init__(
        self,
        options: ClaudeAgentOptions,
        turns: list[list[Step]],
        statuses: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.options = options
        self._turns = turns
        # Each MCP server's settled status, as the turn's init reports it; connected unless named.
        self._statuses = statuses or {}
        self._interrupted = asyncio.Event()
        # Set once a Hang step has written, so a test can stop the turn mid-reply.
        self.hanging = asyncio.Event()
        self._made = 0
        # What Claude Code sent that nobody read yet, which the SDK keeps for the next read.
        self._unread: list[Message] = []

    async def interrupt(self) -> None:
        """Claude Code ends the turn with a result, read or not."""
        self.interrupted = True
        self._unread = [self._result(error=True)]
        self._interrupted.set()

    async def send(
        self, prompt: Any, *, uuid: str | None = None
    ) -> AsyncIterator[Message]:
        self.sent.append(prompt)
        self.uuids.append(uuid)
        for message in self._unread:
            yield message
            if isinstance(message, ResultMessage):
                self._unread = []
                return
        await self._mirror(
            {
                "type": "user",
                "uuid": uuid,
                "message": {"role": "user", "content": prompt},
            }
        )
        yield self._init()
        for step in self._turns.pop(0):
            async for message in self._play(step):
                yield message
                if isinstance(message, ResultMessage):
                    return
        yield self._result()

    async def _play(self, step: Step) -> AsyncIterator[Message]:
        message_id = self._next("msg")
        if isinstance(step, Say | Hang):
            yield AssistantMessage(
                [TextBlock(step.text)], "sonnet", message_id=message_id
            )
            await self._mirror(
                _assistant(message_id, {"type": "text", "text": step.text})
            )
            if isinstance(step, Hang):
                self.hanging.set()
                await self._interrupted.wait()
                # Claude Code takes a moment to end the turn after an interrupt.
                await asyncio.sleep(0.3)
                ended, self._unread = self._unread, []
                yield ended[0]
        elif isinstance(step, Fail):
            yield AssistantMessage(
                [], "sonnet", error=step.error, message_id=message_id
            )
        else:
            call_id = self._next("toolu")
            block = {
                "type": "tool_use",
                "id": call_id,
                "name": step.tool,
                "input": step.input,
            }
            yield AssistantMessage(
                [ToolUseBlock(call_id, step.tool, step.input)],
                "sonnet",
                message_id=message_id,
            )
            await self._mirror(_assistant(message_id, block))
            refusal = await self._gate(step, call_id)
            result = ToolResultBlock(
                call_id, refusal or step.result, is_error=bool(refusal)
            )
            yield UserMessage(content=[result])
            await self._mirror(
                {
                    "type": "user",
                    "uuid": self._next("result"),
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call_id,
                                "content": result.content,
                                "is_error": result.is_error,
                            }
                        ],
                    },
                }
            )

    async def _gate(self, step: Call, call_id: str) -> str | None:
        """The refusal the model reads, or None when the call ran."""
        (matcher,) = self.options.hooks["PreToolUse"]
        decided = await matcher.hooks[0](
            {
                "hook_event_name": "PreToolUse",
                "tool_name": step.tool,
                "tool_input": step.input,
            },
            call_id,
            {},
        )
        verdict = decided["hookSpecificOutput"]
        if verdict["permissionDecision"] == "allow":
            return None
        if verdict["permissionDecision"] == "deny":
            return f"PreToolUse hook error: {verdict['permissionDecisionReason']}"
        answer = await self.options.can_use_tool(
            step.tool, step.input, ToolPermissionContext(tool_use_id=call_id)
        )
        return None if isinstance(answer, PermissionResultAllow) else answer.message

    async def _mirror(self, entry: dict[str, Any]) -> None:
        store = self.options.session_store
        session_id = self.options.session_id or self.options.resume
        entry = {
            "isSidechain": False,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            **entry,
        }
        await store.append({"project_key": "p", "session_id": session_id}, [entry])

    def _init(self) -> SystemMessage:
        """The turn's opening message, once every MCP server has connected or failed."""
        given = json.loads(Path(self.options.mcp_servers).read_text())["mcpServers"]
        servers = [
            {"name": name, "status": self._statuses.get(name, "connected")}
            for name in given
        ]
        return SystemMessage(subtype="init", data={"mcp_servers": servers})

    def _next(self, kind: str) -> str:
        self._made += 1
        return f"{kind}_{self._made}"

    def _result(self, *, error: bool = False) -> ResultMessage:
        return ResultMessage(
            subtype="error_during_execution" if error else "success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=error,
            num_turns=1,
            session_id=self.options.session_id or self.options.resume or "",
        )


def _assistant(message_id: str, block: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "assistant",
        "uuid": f"{message_id}-{block['type']}",
        "message": {"id": message_id, "role": "assistant", "content": [block]},
    }
