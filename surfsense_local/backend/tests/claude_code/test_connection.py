"""The Claude plan connection against the developer's own signed-in Claude Code."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.subscriptions.claude.proxy import serving_claude_proxy
from shared.db import create_session_factory

pytestmark = pytest.mark.claude_code


async def test_this_machines_claude_code_connects_and_lists_its_models(
    client: AsyncClient, engine: Engine, claude_binary: Path
) -> None:
    """End to end on a real install: ready, connected, and the plan's models listed."""
    found = (await client.get("/llm/connections/claude/status")).json()
    assert found["state"] == "ready", found
    assert found["email"]
    assert found["plan"]

    for host in ("api.anthropic.com", "platform.claude.com"):
        await client.put(
            "/egress", json={"destinations": [f"host:{host}"], "enabled": True}
        )
    connection = (
        await client.post("/llm/connections/claude", json={"label": "Claude"})
    ).json()
    async with serving_claude_proxy(create_session_factory(engine), "127.0.0.1"):
        models = (
            await client.get(f"/llm/connections/{connection['id']}/models")
        ).json()

    names = {m["name"] for m in models}
    assert {"claude-opus-5-5", "claude-sonnet-5-5"} <= names
    sonnet = next(m for m in models if m["name"] == "claude-sonnet-5-5")
    assert sonnet["selectable_for"] == ["text_gen"]
    assert sonnet["capability_level"] is not None
