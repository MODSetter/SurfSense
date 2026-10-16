"""A Basic chat answered by the developer's own Claude Code, through the app's API."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.subscriptions.claude.plan_generator import close_claude_runs

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
    client: AsyncClient, claude_binary: Path
) -> None:
    """Connect, choose a Claude plan model, and get two answers that remember."""
    await client.put("/egress/host:api.anthropic.com", json={"enabled": True})
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
