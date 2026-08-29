from __future__ import annotations

import json
import operator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Annotated

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    enqueue_deliverable_job as enqueue_tool,
)

pytestmark = pytest.mark.unit


class _SubagentState(TypedDict, total=False):
    messages: Annotated[list, operator.add]
    receipts: Annotated[list[dict], operator.add]


@pytest.mark.asyncio
async def test_enqueue_receipt_reaches_parent_when_final_text_omits_it(
    monkeypatch,
) -> None:
    class Session:
        async def commit(self) -> None:
            return None

    @asynccontextmanager
    async def session_context():
        yield Session()

    async def create_job(_session, **_kwargs):
        return (
            SimpleNamespace(
                id=19,
                celery_task_id="deliverable-job:19:attempt:1",
            ),
            True,
        )

    monkeypatch.setattr(enqueue_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(enqueue_tool, "create_deliverable_job", create_job)
    enqueue = enqueue_tool.create_enqueue_deliverable_job_tool(
        workspace_id=3,
        dispatcher=lambda **_kwargs: None,
    )

    async def enqueue_node(_state):
        runtime = SimpleNamespace(
            tool_call_id="call-video-1",
            state={},
            config={"configurable": {"thread_id": "44::task:parent-call"}},
        )
        return await enqueue.coroutine(
            title="Product launch",
            brief="Explain the launch clearly",
            source_references=[],
            revision_artifact_id=None,
            runtime=runtime,
        )

    def final_node(_state):
        return {"messages": [AIMessage(content='{"status":"success"}')]}

    graph = StateGraph(_SubagentState)
    graph.add_node("enqueue", enqueue_node)
    graph.add_node("final", final_node)
    graph.add_edge(START, "enqueue")
    graph.add_edge("enqueue", "final")
    graph.add_edge("final", END)
    subagent = graph.compile(checkpointer=InMemorySaver())
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "deliverables",
                "description": "Creates deliverables.",
                "runnable": subagent,
            }
        ]
    )
    prior_receipt = {
        "route": "deliverables",
        "type": "artifact",
        "operation": "generate",
        "status": "success",
        "external_id": "7",
    }
    runtime = ToolRuntime(
        state={
            "messages": [HumanMessage(content="Make a video")],
            "receipts": [prior_receipt],
        },
        context=None,
        config={"configurable": {"thread_id": "44"}},
        stream_writer=None,
        tool_call_id="parent-call",
        store=None,
    )

    result = await task_tool.coroutine(
        description="Make a video",
        subagent_type="deliverables",
        runtime=runtime,
    )

    receipt = {
        "route": "deliverables",
        "type": "deliverable_job",
        "operation": "generate",
        "status": "pending",
        "external_id": "19",
        "preview": "Product launch",
    }
    assert result.update["receipts"] == [receipt]
    task_result = result.update["messages"][0].content
    assert task_result.startswith('{"status":"success"}')
    serialized_receipts = task_result.split("<authoritative_receipts>\n", maxsplit=1)[
        1
    ].split("\n</authoritative_receipts>", maxsplit=1)[0]
    assert json.loads(serialized_receipts) == [receipt]
