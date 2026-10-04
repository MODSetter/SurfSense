"""The agent making documents through the API: its tools and skill, and the steps that show what it made."""

import json

import pytest

from modules.agent.opencode_config import DOCUMENTS_SKILL, skills_folder
from modules.agent.tool_endpoint import render_document
from modules.agent.tool_endpoint.render_document import STOP_RULE
from shared.queue import studio_queue
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import of_type, open_thread, send
from tests.integration.worker.conftest import stub_model  # noqa: F401

# The job indexes what the script wrote; the stub stands in for the embedder.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

WORD = """\
import os
import docx

document = docx.Document()
document.add_heading("Client proposal", level=1)
document.save(os.environ["OUTPUT_PATH"])
"""


def call(name: str, arguments: dict) -> tuple[str, str]:
    """A scripted tool call, as the model would make it."""
    return ("call", json.dumps({"name": name, "arguments": arguments}))


def render(script: str) -> tuple[str, str]:
    """A scripted call to render a Word document from this script."""
    return call(
        "surfsense_render_document",
        {"title": "Client proposal", "format": "docx", "script": script},
    )


def _finished(frames: list[dict], tool: str) -> dict:
    """The last frame of a step that reached its end."""
    (step,) = [
        frame
        for frame in of_type(frames, "agent-step")
        if frame["tool"] == tool and frame["status"] in ("completed", "error")
    ]
    return step


def _tool_results(request: dict) -> str:
    """What the model was handed back from its tool calls."""
    return json.dumps([m for m in request["messages"] if m["role"] == "tool"])


async def test_the_agent_is_offered_its_document_tools_and_skill_but_no_shell(
    agent_api: AgentAPI,
) -> None:
    """Documents are made through SurfSense's tools, taught by SurfSense's one skill."""
    agent_api.model.replies = [("text", "Hello.")]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "Hi")

    (request,) = agent_api.model.requests
    offered = [tool["function"]["name"] for tool in request["tools"]]
    for tool in (
        "surfsense_render_document",
        "surfsense_read_document",
        "surfsense_list_images",
        "skill",
    ):
        assert tool in offered, tool
    assert "bash" not in offered
    prompt = json.dumps(request["messages"])
    assert f"<name>{DOCUMENTS_SKILL}</name>" in prompt
    assert "customize-opencode" not in prompt


async def test_the_agent_loads_its_skill_and_may_read_the_folder_it_is_in(
    agent_api: AgentAPI,
) -> None:
    """A skill can point at files beside it, outside the agent's own folder."""
    skill_file = skills_folder().resolve() / DOCUMENTS_SKILL / "SKILL.md"
    agent_api.model.replies = [
        call("skill", {"name": DOCUMENTS_SKILL}),
        call("read", {"filePath": str(skill_file)}),
        ("text", "Ready."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Make a Word document")

    loaded = _finished(frames, "skill")
    assert loaded["status"] == "completed"
    assert "OUTPUT_PATH" in loaded["output"]
    assert _finished(frames, "read")["status"] == "completed"
    assert not of_type(frames, "permission-request")


async def test_a_render_step_links_the_version_it_made(
    agent_api: AgentAPI, studio_worker: None
) -> None:
    """The thread opens the document in Studio, live and when reopened."""
    agent_api.model.replies = [render(WORD), ("text", "Made it.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal")
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
    listed = await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")

    (artifact,) = listed.json()
    made = {"id": artifact["id"], "title": "Client proposal", "version": 1}
    step = _finished(frames, "surfsense_render_document")
    assert (step["status"], step["artifact"]) == ("completed", made)
    (stored_step,) = stored.json()[-1]["content"]["steps"]
    assert stored_step["artifact"] == made
    assert "Rendered artifact" in _tool_results(agent_api.model.requests[1])


async def test_a_failed_render_reaches_the_model_with_the_stop_rule(
    agent_api: AgentAPI, studio_worker: None
) -> None:
    """The model reads the traceback to fix its script, and the rule to stop at three."""
    agent_api.model.replies = [
        render("raise ValueError('the pricing table is empty')\n"),
        ("text", "It failed."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal")

    step = _finished(frames, "surfsense_render_document")
    assert (step["status"], step["artifact"]) == ("error", None)
    handed_back = _tool_results(agent_api.model.requests[1])
    assert "ValueError: the pricing table is empty" in handed_back
    assert STOP_RULE in handed_back


async def test_a_render_ready_after_its_call_answered_links_its_version_when_read_back(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Studio may be busy past the call's wait; the step links the version once it is made."""
    monkeypatch.setattr(render_document, "WAIT_SECONDS", 0.5)
    agent_api.model.replies = [render(WORD), ("text", "It is on its way.")]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal")
    step = _finished(frames, "surfsense_render_document")
    assert (step["status"], step["artifact"]) == ("completed", None)
    studio_queue.execute(studio_queue.dequeue())  # Studio gets to it after the turn
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
    listed = await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")

    (artifact,) = listed.json()
    assert artifact["status"] == "ready"
    (stored_step,) = stored.json()[-1]["content"]["steps"]
    assert stored_step["artifact"] == {
        "id": artifact["id"],
        "title": "Client proposal",
        "version": 1,
    }
