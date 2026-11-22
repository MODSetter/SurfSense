import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, Message

from modules.llm.subscriptions.claude.tested_version import note_untested

# A user message given as content blocks, such as a handover note beside the text.
Prompt = str | list[dict[str, Any]]


class ClaudeRun(Protocol):
    """One running Claude Code. Everything else talks to Claude Code through this."""

    def send(
        self, prompt: Prompt, *, uuid: str | None = None
    ) -> AsyncIterator[Message]:
        """Send a user message and yield what follows, up to its `ResultMessage`.

        `uuid` names the message in the transcript, so a turn read back keeps the
        id its live frames used.
        """
        ...

    async def interrupt(self) -> None: ...

    async def models(self) -> list[dict[str, Any]]: ...

    async def reconnect(self, server: str) -> None:
        """Connect an MCP server again, so its tools are listed anew."""
        ...

    async def close(self) -> None: ...


async def _as_user_message(
    blocks: list[dict[str, Any]], uuid: str | None
) -> AsyncIterator[dict]:
    message = {
        "type": "user",
        "message": {"role": "user", "content": blocks},
        "parent_tool_use_id": None,
    }
    yield message if uuid is None else {**message, "uuid": uuid}


class _SdkRun:
    def __init__(self, client: ClaudeSDKClient) -> None:
        self._client = client

    async def send(
        self, prompt: Prompt, *, uuid: str | None = None
    ) -> AsyncIterator[Message]:
        if isinstance(prompt, str):
            prompt = [{"type": "text", "text": prompt}] if uuid else prompt
        await self._client.query(
            prompt if isinstance(prompt, str) else _as_user_message(prompt, uuid)
        )
        async for message in self._client.receive_response():
            yield message

    async def interrupt(self) -> None:
        await self._client.interrupt()

    async def models(self) -> list[dict[str, Any]]:
        info = await self._client.get_server_info()
        return list((info or {}).get("models", []))

    async def reconnect(self, server: str) -> None:
        await self._client.reconnect_mcp_server(server)

    async def close(self) -> None:
        await self._client.disconnect()


async def open_run(options: ClaudeAgentOptions) -> ClaudeRun:
    """Start Claude Code with options from `launch_options`."""
    if options.cli_path is not None:
        await asyncio.to_thread(note_untested, Path(options.cli_path))
    client = ClaudeSDKClient(options)
    await client.connect()
    return _SdkRun(client)
