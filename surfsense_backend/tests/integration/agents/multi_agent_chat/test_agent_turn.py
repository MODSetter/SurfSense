"""Guardrail D: the real multi-agent is still assemblable and runnable.

Builds the production ``create_multi_agent_chat_deep_agent`` factory against a
real (test) DB with a scripted LLM, then drives one turn. This is the only
guard that proves the *assembled* agent — full tool registry, middleware stack,
compiled graph — still executes end to end after files move. A/B/C prove the
parts import, wire, and load; this proves they run together.

Scripted LLM + faked external tools; everything we own (graph, middleware,
DB-backed connector service) runs for real.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.services.connector_service import ConnectorService
from tests.integration.harness import (
    ScriptedTurn,
    StubToolSpec,
    build_scripted_harness,
)

pytestmark = pytest.mark.integration


def _last_ai_text(messages: list) -> str | None:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
    return None


@pytest.mark.asyncio
async def test_agent_runs_a_scripted_text_turn(db_session, db_user, db_search_space):
    """A freshly assembled agent streams a scripted final-text turn to completion."""
    harness = build_scripted_harness(turns=[ScriptedTurn(text="done")])

    agent = await create_multi_agent_chat_deep_agent(
        llm=harness.model,
        search_space_id=db_search_space.id,
        db_session=db_session,
        connector_service=ConnectorService(db_session),
        checkpointer=InMemorySaver(),
        user_id=str(db_user.id),
        thread_id=db_search_space.id,
        agent_config=None,
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="hello")]},
        config={"configurable": {"thread_id": "guard-d-thread-1"}},
    )

    assert _last_ai_text(result["messages"]) == "done"


@pytest.mark.asyncio
async def test_agent_routes_a_scripted_tool_call(db_session, db_user, db_search_space):
    """The compiled graph routes a model tool call to its tool and resumes."""
    harness = build_scripted_harness(
        turns=[
            ScriptedTurn(
                tool_calls=[{"name": "echo", "args": {"x": 1}, "id": "call_1"}]
            ),
            ScriptedTurn(text="echoed"),
        ],
        tools=[
            StubToolSpec(
                name="echo",
                description="Echo the args back.",
                handler=lambda **kwargs: {"echoed": kwargs},
            ),
        ],
    )

    agent = await create_multi_agent_chat_deep_agent(
        llm=harness.model,
        search_space_id=db_search_space.id,
        db_session=db_session,
        connector_service=ConnectorService(db_session),
        checkpointer=InMemorySaver(),
        user_id=str(db_user.id),
        thread_id=db_search_space.id,
        agent_config=None,
        additional_tools=harness.tools,
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="echo please")]},
        config={"configurable": {"thread_id": "guard-d-thread-2"}},
    )

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert any("echoed" in str(m.content) for m in tool_messages)
    assert _last_ai_text(result["messages"]) == "echoed"


@pytest.mark.asyncio
async def test_agent_checkpoint_round_trips_across_turns(
    db_session, db_user, db_search_space
):
    """Turn 2 sees turn 1's history, proving the checkpoint serializes and reloads.

    Uses InMemorySaver, which serializes via the same ``JsonPlusSerializer`` as
    the production Postgres checkpointer — so a state class that became
    unserializable after a module move would fail here too.
    """
    harness = build_scripted_harness(
        turns=[ScriptedTurn(text="ok-one"), ScriptedTurn(text="ok-two")]
    )
    checkpointer = InMemorySaver()
    config = {"configurable": {"thread_id": "guard-e-thread-1"}}

    async def _build():
        return await create_multi_agent_chat_deep_agent(
            llm=harness.model,
            search_space_id=db_search_space.id,
            db_session=db_session,
            connector_service=ConnectorService(db_session),
            checkpointer=checkpointer,
            user_id=str(db_user.id),
            thread_id=db_search_space.id,
            agent_config=None,
        )

    agent = await _build()
    first = await agent.ainvoke(
        {"messages": [HumanMessage(content="remember apple")]}, config
    )
    second = await agent.ainvoke(
        {"messages": [HumanMessage(content="second turn")]}, config
    )

    texts = [
        m.content for m in second["messages"] if isinstance(m, HumanMessage)
    ]
    assert "remember apple" in texts, "turn 1 history not reloaded from checkpoint"
    assert len(second["messages"]) > len(first["messages"])
