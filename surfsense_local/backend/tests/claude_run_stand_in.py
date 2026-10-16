"""A ClaudeRun that replays what a real Claude Code run sent, without starting one."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from claude_agent_sdk import Message

# What Claude Code 2.1.301 on a Max plan listed on 16 Oct 2026.
MAX_PLAN_MODELS: list[dict[str, Any]] = [
    {
        "value": "default",
        "resolvedModel": "claude-opus-5-5",
        "displayName": "Default (recommended)",
    },
    {"value": "opus", "resolvedModel": "claude-opus-5-5", "displayName": "Opus"},
    {
        "value": "claude-fable-5-1[1m]",
        "resolvedModel": "claude-fable-5-1",
        "displayName": "Fable",
    },
    {"value": "sonnet", "resolvedModel": "claude-sonnet-5-5", "displayName": "Sonnet"},
    {"value": "haiku", "resolvedModel": "claude-haiku-5-5", "displayName": "Haiku"},
]


class ScriptedRun:
    """Answers each `send` with the next scripted reply, and records what it was sent."""

    def __init__(
        self,
        replies: Sequence[Sequence[Message]] = (),
        models: list[dict[str, Any]] | None = None,
    ) -> None:
        self.replies = list(replies)
        self.sent: list[Any] = []
        self.interrupted = False
        self.closed = False
        self._models = MAX_PLAN_MODELS if models is None else models

    async def send(self, prompt: Any) -> AsyncIterator[Message]:
        """Yield the next scripted reply."""
        self.sent.append(prompt)
        for message in self.replies.pop(0):
            yield message

    async def interrupt(self) -> None:
        """Record that the turn was stopped."""
        self.interrupted = True

    async def models(self) -> list[dict[str, Any]]:
        """The scripted model list."""
        return self._models

    async def close(self) -> None:
        """Record that the run was closed."""
        self.closed = True
