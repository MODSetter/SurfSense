"""An Agentic turn is counted once its engine takes it, and as an answer only once it ends with text.

On the stand-in Claude Code, so CI drives the route's counting without opencode or a model.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from modules.usage_statistics.activity_counts import Activity, read_counts
from tests.claude_agent_stand_in import Fail, Say
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.claude_code.test_claude_agent import (
    _agentic_thread,
    _send,
)

pytestmark = pytest.mark.integration


async def test_a_turn_that_ends_with_text_counts_a_turn_and_a_remote_answer(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """A Claude plan is a connection, so its answer is remote; nothing of the question is kept."""
    claude_agent.turns = [[Say("Revenue grew 12%.")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "What grew in Q3?")

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.AGENT_TURN, since) == 1
    assert counts.total(Activity.REMOTE_ANSWER, since) == 1
    assert counts.total(Activity.LOCAL_ANSWER, since) == 0
    assert counts.answered
    assert "Q3" not in str(counts.hours)


async def test_a_turn_that_fails_counts_a_turn_and_no_answer(
    client: AsyncClient, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """A failed first turn must not read as setup's first answer."""
    claude_agent.turns = [[Fail("authentication_failed")]]
    thread = await _agentic_thread(client, claude_on_this_machine)

    await _send(client, thread["id"], "Hello")

    counts = read_counts()
    assert counts is not None
    since = datetime.now(UTC) - timedelta(hours=1)
    assert counts.total(Activity.AGENT_TURN, since) == 1
    assert counts.total(Activity.REMOTE_ANSWER, since) == 0
    assert not counts.answered
