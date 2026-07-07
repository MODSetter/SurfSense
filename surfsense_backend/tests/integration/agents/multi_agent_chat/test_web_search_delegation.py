"""Backend E2E: public web search now flows through the ``google_search`` route.

After the Google-only consolidation the main agent has no ``web_search`` tool;
a web query must be delegated to the ``google_search`` subagent via ``task``.
This drives the *assembled* production graph (real DB, scripted LLM) end to end:
main agent emits a ``task(google_search, ...)`` call, the subagent runs a turn,
and the main agent resumes to a final answer. Proves the delegation path the
teardown relies on actually executes -- not just that the constants changed.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.services.connector_service import ConnectorService
from tests.integration.harness import ScriptedTurn, build_scripted_harness

pytestmark = pytest.mark.integration


def _last_ai_text(messages: list) -> str | None:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content:
            return m.content
    return None


@pytest.mark.asyncio
async def test_web_query_delegates_to_google_search(db_session, db_user, db_workspace):
    """A web-search query routes through ``task(google_search)`` and resumes.

    Scripted sequence (the fake model is shared and consumed in order across the
    main agent and the delegated subagent):
      1. main agent  -> task(subagent_type="google_search")
      2. subagent    -> plain text (never touches the scrape tool, so no network)
      3. main agent  -> final answer
    """
    harness = build_scripted_harness(
        turns=[
            ScriptedTurn(
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "subagent_type": "google_search",
                            "description": "latest SurfSense release notes",
                        },
                        "id": "call_ws_task",
                    }
                ]
            ),
            ScriptedTurn(text="SERP: SurfSense v2 shipped Google-only web search."),
            ScriptedTurn(text="SurfSense v2 shipped Google-only web search."),
        ]
    )

    agent = await create_multi_agent_chat_deep_agent(
        llm=harness.model,
        workspace_id=db_workspace.id,
        db_session=db_session,
        connector_service=ConnectorService(db_session),
        checkpointer=InMemorySaver(),
        user_id=str(db_user.id),
        thread_id=db_workspace.id,
        agent_config=None,
    )

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="search the web for SurfSense news")]},
        config={"configurable": {"thread_id": "ws-google-delegation-1"}},
    )

    task_tool_messages = [
        m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "task"
    ]
    assert task_tool_messages, "web query did not delegate through the task tool"
    assert _last_ai_text(result["messages"]) == (
        "SurfSense v2 shipped Google-only web search."
    )
