"""A Basic chat answered by the developer's own Claude Code, through the app's API."""

import json
import logging
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.subscriptions.claude.plan_generator import close_claude_runs
from modules.llm.subscriptions.claude.proxy import serving_claude_proxy
from shared.db import create_session_factory

pytestmark = pytest.mark.claude_code
HAIKU = "claude-haiku-5-5"


async def _send(client: AsyncClient, thread_id: int, text: str) -> list[dict]:
    frames: list[dict] = []
    async with client.stream(
        "POST", f"/chat/threads/{thread_id}/messages", json={"text": text}
    ) as reply:
        assert reply.status_code == 200
        async for line in reply.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                frames.append(json.loads(line[len("data: ") :]))
    return frames


@pytest.mark.usefixtures("real_model")
async def test_a_basic_chat_is_answered_by_this_machines_claude_code(
    client: AsyncClient,
    engine: Engine,
    claude_binary: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Connect, choose a Claude plan model, and get two answers that remember,
    with every connection Claude Code makes going through SurfSense's proxy."""
    caplog.set_level(logging.INFO)
    async with serving_claude_proxy(create_session_factory(engine), "127.0.0.1"):
        for host in ("api.anthropic.com", "platform.claude.com"):
            await client.put(
                "/egress", json={"destinations": [f"host:{host}"], "enabled": True}
            )
        connection = (
            await client.post("/llm/connections/claude", json={"label": "Claude"})
        ).json()
        chosen = await client.put(
            "/llm/selection/text_gen",
            json={
                "provider": "openai_compatible",
                "connection_id": connection["id"],
                "name": HAIKU,
            },
        )
        assert chosen.status_code == 200, chosen.text
        workspace = (await client.post("/workspaces", json={"name": "w"})).json()
        thread_id = (
            await client.post(
                f"/workspaces/{workspace['id']}/chat/threads", json={"mode": "basic"}
            )
        ).json()["id"]

        try:
            first = await _send(
                client, thread_id, "My cat is called Biscuit. Reply in one word: ok."
            )
            second = await _send(client, thread_id, "What is my cat called? One word.")
        finally:
            await close_claude_runs()

    assert not [f for f in first + second if f.get("type") == "error"], first + second
    answer = "".join(f["text"] for f in second if f.get("type") == "delta")
    assert "biscuit" in answer.lower()
    # Each tunnel is logged with its host as the first argument.
    tunnelled = {
        record.args[0]
        for record in caplog.records
        if record.name == "modules.agent.runtime_proxy.server"
        and record.msg.startswith("tunnel to %s:%s: checked")
    }
    assert tunnelled == {"api.anthropic.com"}
    assert "refused" not in caplog.text
