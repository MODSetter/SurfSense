"""A ClaudeRun that replays what a real Claude Code run sent, without starting one."""

from collections.abc import AsyncIterator, Callable, Sequence
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
        respond: Callable[[Any], Sequence[Message]] | None = None,
    ) -> None:
        self.replies = list(replies)
        # Answers what the script does not, from what was sent.
        self._respond = respond
        self.sent: list[Any] = []
        self.uuids: list[str | None] = []
        self.interrupted = False
        self.closed = False
        # Each MCP server reconnected, by name, in order.
        self.reconnected: list[str] = []
        self._models = MAX_PLAN_MODELS if models is None else models

    async def send(
        self, prompt: Any, *, uuid: str | None = None
    ) -> AsyncIterator[Message]:
        """Yield the next scripted reply."""
        self.sent.append(prompt)
        self.uuids.append(uuid)
        reply = (
            self.replies.pop(0)
            if self.replies or not self._respond
            else self._respond(prompt)
        )
        for message in reply:
            yield message

    async def interrupt(self) -> None:
        """Record that the turn was stopped."""
        self.interrupted = True

    async def models(self) -> list[dict[str, Any]]:
        """The scripted model list."""
        return self._models

    async def reconnect(self, server: str) -> None:
        """Record that a server was connected again."""
        self.reconnected.append(server)

    async def close(self) -> None:
        """Record that the run was closed."""
        self.closed = True


def _event(event: dict[str, Any]) -> Message:
    from claude_agent_sdk import StreamEvent

    return StreamEvent(uuid="e", session_id="s", event=event)


def done(*, structured_output: Any = None, is_error: bool = False) -> Message:
    """The `ResultMessage` every reply ends with."""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="error_during_execution" if is_error else "success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="s",
        structured_output=structured_output,
    )


# When the plan's five-hour window measured on 17 Oct 2026 reset.
RESETS_AT = 1792232400


def plan_limits(*, using_extra: bool) -> Message:
    """Claude Code's rate-limit event, sent with each reply: within the plan, or past it on extra usage.

    Within the plan is as measured (extra usage off for the organization). Past it
    is as Claude Code 2.1.301 builds the event from Anthropic's headers: the plan's
    own status `rejected`, extra usage `allowed`, so `isUsingOverage`.
    """
    from claude_agent_sdk import RateLimitEvent, RateLimitInfo

    status = "rejected" if using_extra else "allowed"
    overage = "allowed" if using_extra else "rejected"
    raw = {
        "status": status,
        "resetsAt": RESETS_AT,
        "rateLimitType": "five_hour",
        "overageStatus": overage,
        "isUsingOverage": using_extra,
    }
    info = RateLimitInfo(
        status=status,
        resets_at=RESETS_AT,
        rate_limit_type="five_hour",
        overage_status=overage,
        raw=raw,
    )
    return RateLimitEvent(info, "limit", "s")


def answer(*chunks: str, thinking: Sequence[str] = ()) -> list[Message]:
    """A reply streamed as Claude Code streams one: thinking first, then text."""
    events: list[Message] = []
    for piece in thinking:
        events.append(
            _event(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "thinking_delta", "thinking": piece},
                }
            )
        )
    for piece in chunks:
        events.append(
            _event(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": piece},
                }
            )
        )
    return [*events, done()]
