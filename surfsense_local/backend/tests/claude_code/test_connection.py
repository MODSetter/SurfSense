"""The Claude plan connection against the developer's own signed-in Claude Code."""

from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.claude_code


async def test_this_machines_claude_code_connects_and_lists_its_models(
    client: AsyncClient, claude_binary: Path
) -> None:
    """End to end on a real install: ready, connected, and the plan's models listed."""
    option = (await client.get("/llm/connections/claude")).json()
    assert option["state"] == "ready", option
    assert option["email"]
    assert option["plan"]

    await client.put("/egress/host:api.anthropic.com", json={"enabled": True})
    connection = (
        await client.post("/llm/connections/claude", json={"label": "Claude"})
    ).json()
    models = (await client.get(f"/llm/connections/{connection['id']}/models")).json()

    names = {m["name"] for m in models}
    assert {"claude-opus-5-5", "claude-sonnet-5-5"} <= names
    sonnet = next(m for m in models if m["name"] == "claude-sonnet-5-5")
    assert sonnet["selectable_for"] == ["text_gen"]
    assert sonnet["capability_level"] is not None
