from collections.abc import AsyncIterator
from typing import Any, Protocol

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, Message

# A user message given as content blocks, such as a handover note beside the text.
Prompt = str | list[dict[str, Any]]


class ClaudeRun(Protocol):
    """One running Claude Code. Everything else talks to Claude Code through this."""

    def send(self, prompt: Prompt) -> AsyncIterator[Message]:
        """Send a user message and yield what follows, up to its `ResultMessage`."""
        ...

    async def interrupt(self) -> None: ...

    async def models(self) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


async def _as_user_message(blocks: list[dict[str, Any]]) -> AsyncIterator[dict]:
    yield {
        "type": "user",
        "message": {"role": "user", "content": blocks},
        "parent_tool_use_id": None,
    }


class _SdkRun:
    def __init__(self, client: ClaudeSDKClient) -> None:
        self._client = client

    async def send(self, prompt: Prompt) -> AsyncIterator[Message]:
        await self._client.query(
            prompt if isinstance(prompt, str) else _as_user_message(prompt)
        )
        async for message in self._client.receive_response():
            yield message

    async def interrupt(self) -> None:
        await self._client.interrupt()

    async def models(self) -> list[dict[str, Any]]:
        info = await self._client.get_server_info()
        return list((info or {}).get("models", []))

    async def close(self) -> None:
        await self._client.disconnect()


async def open_run(options: ClaudeAgentOptions) -> ClaudeRun:
    """Start Claude Code with options from `launch_options`."""
    client = ClaudeSDKClient(options)
    await client.connect()
    return _SdkRun(client)
