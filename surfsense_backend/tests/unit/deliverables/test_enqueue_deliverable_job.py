from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools import (
    enqueue_deliverable_job as enqueue_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.deliverables.tools.index import (
    config,
    load_tools,
)
from app.tasks.chat.streaming.handlers.tools.deliverables.enqueue_deliverable_job.emission import (
    public_enqueue_payload,
)

pytestmark = pytest.mark.unit


def test_streaming_payload_preserves_only_live_card_identity() -> None:
    payload = public_enqueue_payload(
        json.dumps(
            {
                "status": "pending",
                "job_id": 19,
                "title": "Product launch",
                "message": "Your video is being generated.",
                "internal_error": "secret",
            }
        )
    )

    assert payload == {
        "status": "pending",
        "job_id": 19,
        "title": "Product launch",
        "message": "Your video is being generated.",
    }


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        tool_call_id="call-video-1",
        state={},
        config={"configurable": {"thread_id": "44::task:call-video-1"}},
    )


def _payload(command) -> dict:
    return json.loads(command.update["messages"][0].content)


def test_interactive_video_registration_enqueues_only(monkeypatch) -> None:
    monkeypatch.setattr("app.sandbox.is_sandbox_enabled", lambda: True)
    monkeypatch.setattr(config, "VIDEO_SANDBOX_RENDERING_ENABLED", True)
    dependencies = {"workspace_id": 3, "db_session": object()}

    tools = load_tools(dependencies=dependencies)
    names = {tool.name for tool in tools}

    assert "enqueue_deliverable_job" in names
    assert "synthesize_narration" not in names
    assert "prepare_video_project" not in names
    assert "review_video_stills" not in names
    assert "generate_video_presentation" not in names
    enqueue = next(tool for tool in tools if tool.name == "enqueue_deliverable_job")
    assert set(enqueue.args) == {
        "title",
        "brief",
        "source_references",
        "revision_artifact_id",
    }


async def test_enqueue_is_idempotent_normalized_and_sanitized(
    monkeypatch,
) -> None:
    requests = []
    created_values = iter((True, False))

    class Session:
        async def commit(self) -> None:
            return None

    @asynccontextmanager
    async def session_context():
        yield Session()

    async def create_job(_session, **kwargs):
        requests.append(kwargs)
        return (
            SimpleNamespace(
                id=19,
                celery_task_id="deliverable-job:19:attempt:1",
            ),
            next(created_values),
        )

    dispatches = []

    def dispatch(**kwargs) -> None:
        dispatches.append(kwargs)
        raise RuntimeError("amqp://user:secret@broker/internal")

    monkeypatch.setattr(enqueue_tool, "shielded_async_session", session_context)
    monkeypatch.setattr(enqueue_tool, "create_deliverable_job", create_job)
    tool = enqueue_tool.create_enqueue_deliverable_job_tool(
        workspace_id=3,
        dispatcher=dispatch,
    )

    first = await tool.coroutine(
        title="  Product   launch  ",
        brief="  Explain   the launch \n clearly ",
        source_references=[" /documents/brief.md ", "/documents/brief.md", " "],
        revision_artifact_id=None,
        runtime=_runtime(),
    )
    second = await tool.coroutine(
        title="Product launch",
        brief="Explain the launch clearly",
        source_references=["/documents/brief.md"],
        revision_artifact_id=None,
        runtime=_runtime(),
    )

    assert len(dispatches) == 1
    assert requests[0]["tool_call_id"] == "call-video-1"
    assert requests[0]["thread_id"] == 44
    assert requests[0]["request"] == {
        "version": 1,
        "brief": "Explain the launch clearly",
        "source_references": ["/documents/brief.md"],
        "revision_artifact_id": None,
        "root_thread_id": 44,
    }
    for command in (first, second):
        payload = _payload(command)
        assert payload == {
            "status": "pending",
            "job_id": 19,
            "title": "Product launch",
            "message": "Your video is being generated. You can continue chatting.",
        }
        assert "secret" not in str(command)
        assert command.update["receipts"][0]["status"] == "pending"
