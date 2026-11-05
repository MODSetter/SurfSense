"""Claude Code is told of a source named with `@`, as opencode is."""

import pytest
from sqlalchemy import Engine

from tests.claude_agent_stand_in import Say
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.claude_code.test_handover import _choose_claude
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import (
    ingest_note,
    open_thread,
    send,
)

pytestmark = pytest.mark.integration


async def test_claude_code_is_told_of_a_named_source_before_the_users_words(
    agent_api: AgentAPI,
    engine: Engine,
    claude_on_this_machine,
    claude_agent: ClaudeAgent,
    real_model: object,
) -> None:
    """Both engines start a turn from the same sources and the same note."""
    await _choose_claude(agent_api, claude_on_this_machine)
    named, _ = ingest_note(engine, agent_api.workspace_id, "Memo", "Ship on Monday.")
    thread = await open_thread(agent_api, mode="agentic")
    claude_agent.turns = [[Say("Monday.")]]

    await send(
        agent_api,
        thread["id"],
        "When per @Memo?",
        source_scope={"all": True},
        mentioned_sources={
            "document_ids": [named],
            "chips": [{"id": f"document:{named}", "at": 9, "length": 5}],
        },
    )

    (run,) = claude_agent.started
    (blocks,) = run.sent
    assert "The user named these sources" in blocks[0]["text"]
    assert f"Memo [{named}].md" in blocks[0]["text"]
    assert blocks[-1]["text"] == "When per @Memo?"
    stored = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert stored[0]["content"]["text"] == "When per @Memo?"
    assert stored[0]["content"]["mentions"] == [
        {
            "id": f"document:{named}",
            "type": "source",
            "label": "Memo",
            "at": 9,
            "length": 5,
        }
    ]
