"""A thread's Claude session is resumed only under the Claude account that made it."""

import pytest

from tests.claude_agent_stand_in import Say
from tests.claude_stand_in import SIGNED_IN
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.claude_code.test_handover import _choose_claude
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import of_type, open_thread, send

pytestmark = pytest.mark.integration
GRACE = {**SIGNED_IN, "email": "grace@example.com", "orgId": "org-grace"}


async def test_another_account_starts_a_new_session_told_the_whole_thread(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The new account's session is told every earlier turn, and the thread reads as one."""
    await _choose_claude(agent_api, claude_on_this_machine)
    thread = await open_thread(agent_api, mode="agentic")
    claude_agent.turns = [[Say("Q3 grew 12%.")], [Say("Yes, 12%.")]]
    await send(agent_api, thread["id"], "What grew in Q3?")

    claude_on_this_machine(auth=GRACE)
    frames = await send(agent_api, thread["id"], "Are you sure?")

    assert of_type(frames, "completed")[0]["text"] == "Yes, 12%."
    first, second = claude_agent.started
    assert second.options.resume is None
    assert second.options.session_id != first.options.session_id
    (sent,) = second.sent
    note, words = sent[0]["text"], sent[-1]["text"]
    assert note.startswith("<surfsense-handover>")
    assert "What grew in Q3?" in note
    assert "Q3 grew 12%." in note
    assert words == "Are you sure?"
    listed = (await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")).json()
    assert [turn["content"]["text"] for turn in listed] == [
        "What grew in Q3?",
        "Q3 grew 12%.",
        "Are you sure?",
        "Yes, 12%.",
    ]


async def test_the_same_account_resumes_its_session(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Its running Claude Code answers the next turn, given no note."""
    await _choose_claude(agent_api, claude_on_this_machine)
    thread = await open_thread(agent_api, mode="agentic")
    claude_agent.turns = [[Say("One.")], [Say("Two.")]]
    await send(agent_api, thread["id"], "First")

    await send(agent_api, thread["id"], "Second")

    (run,) = claude_agent.started
    assert [blocks[-1]["text"] for blocks in run.sent] == ["First", "Second"]
    assert all(len(blocks) == 1 for blocks in run.sent)
