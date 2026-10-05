"""The agent making documents through the API: its tools and skill, and the steps that show what it made."""

import json
import sqlite3

import pytest
from sqlalchemy.exc import OperationalError

from modules.agent.agent_threads import ready_renders
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
FAILING = "raise ValueError('the pricing table is empty')\n"


def call(name: str, arguments: dict) -> tuple[str, str]:
    """A scripted tool call, as the model would make it."""
    return ("call", json.dumps({"name": name, "arguments": arguments}))


def render(script: str, artifact_id: int | None = None) -> tuple[str, str]:
    """A scripted call to render a Word document from this script."""
    arguments = {"title": "Client proposal", "format": "docx", "script": script}
    if artifact_id is not None:
        arguments["artifact_id"] = artifact_id
    return call("surfsense_render_document", arguments)


def _finished(frames: list[dict], tool: str) -> dict:
    """The last frame of a step that reached its end."""
    (step,) = [
        frame
        for frame in of_type(frames, "agent-step")
        if frame["tool"] == tool and frame["status"] in ("completed", "error")
    ]
    return step


def _last_tool_result(request: dict) -> str:
    """What the model was handed back from its latest tool call."""
    return json.dumps([m for m in request["messages"] if m["role"] == "tool"][-1])


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
    made = {
        "id": artifact["id"],
        "title": "Client proposal",
        "version": 1,
        "created": True,
    }
    step = _finished(frames, "surfsense_render_document")
    assert (step["status"], step["artifact"]) == ("completed", made)
    (stored_step,) = stored.json()[-1]["content"]["steps"]
    assert stored_step["artifact"] == made
    assert "Rendered artifact" in _tool_results(agent_api.model.requests[1])


async def test_a_documents_first_ready_version_is_created_and_the_next_updates_it(
    agent_api: AgentAPI, studio_worker: None
) -> None:
    """A failed first try made nothing the user had, so the version after it is the new document."""
    thread = await open_thread(agent_api)

    async def render_turn(*replies: tuple[str, str]) -> tuple[dict, dict]:
        agent_api.model.replies = [*replies, ("text", "Done.")]
        frames = await send(agent_api, thread["id"], "Draft the proposal")
        stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")
        (stored_step,) = stored.json()[-1]["content"]["steps"]
        return _finished(frames, "surfsense_render_document"), stored_step

    await render_turn(render(FAILING))
    listed = await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")
    (failed,) = listed.json()
    fixed, fixed_stored = await render_turn(render(WORD, artifact_id=failed["id"]))
    edited, edited_stored = await render_turn(
        render(WORD, artifact_id=fixed["artifact"]["id"])
    )

    assert (fixed["artifact"]["version"], fixed["artifact"]["created"]) == (2, True)
    assert fixed_stored["artifact"] == fixed["artifact"]
    assert (edited["artifact"]["version"], edited["artifact"]["created"]) == (3, False)
    assert edited_stored["artifact"] == edited["artifact"]


async def test_an_edit_stays_an_update_while_the_version_it_edited_runs_again(
    agent_api: AgentAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Studio's Regenerate puts a ready version back in the queue; the user still had it."""
    monkeypatch.setattr(render_document, "WAIT_SECONDS", 0.5)
    thread = await open_thread(agent_api)

    async def render_turn(reply: tuple[str, str]) -> None:
        agent_api.model.replies = [reply, ("text", "Done.")]
        await send(agent_api, thread["id"], "Draft the proposal")
        studio_queue.execute(studio_queue.dequeue())

    await render_turn(render(WORD))
    (first,) = (
        await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")
    ).json()
    await render_turn(render(WORD, artifact_id=first["id"]))
    rerun = await agent_api.http.post(f"/artifacts/{first['id']}/regenerate")
    assert rerun.status_code == 202, rerun.text
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    (edit,) = stored.json()[-1]["content"]["steps"]
    assert (edit["artifact"]["version"], edit["artifact"]["created"]) == (2, False)


async def test_a_locked_database_never_stops_the_turn_to_say_whether_a_render_created(
    agent_api: AgentAPI, studio_worker: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Studio can hold the write lock past the busy wait; the live step goes out unlabelled."""

    def locked(*_: object) -> bool:
        raise OperationalError(
            "SELECT", {}, sqlite3.OperationalError("database is locked")
        )

    agent_api.model.replies = [render(WORD), ("text", "Made it.")]
    thread = await open_thread(agent_api)

    with monkeypatch.context() as busy:
        busy.setattr(ready_renders, "_first_ready", locked)
        frames = await send(agent_api, thread["id"], "Draft the proposal")
    stored = await agent_api.http.get(f"/chat/threads/{thread['id']}/messages")

    step = _finished(frames, "surfsense_render_document")
    assert (step["artifact"]["version"], "created" in step["artifact"]) == (1, False)
    assert of_type(frames, "completed")[0]["text"] == "Made it."
    (stored_step,) = stored.json()[-1]["content"]["steps"]
    assert stored_step["artifact"]["created"] is True


async def test_a_failed_render_reaches_the_model_with_the_stop_rule(
    agent_api: AgentAPI, studio_worker: None
) -> None:
    """The model reads the traceback to fix its script, and the rule to stop at three."""
    agent_api.model.replies = [
        render(FAILING),
        ("text", "It failed."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Draft the proposal")

    step = _finished(frames, "surfsense_render_document")
    assert (step["status"], step["artifact"]) == ("error", None)
    handed_back = _tool_results(agent_api.model.requests[1])
    assert "ValueError: the pricing table is empty" in handed_back
    assert STOP_RULE in handed_back


async def test_three_failed_renders_stop_the_turn_and_the_next_turn_may_render_again(
    agent_api: AgentAPI, studio_worker: None
) -> None:
    """The stop holds for the turn alone: the user's next message may ask for another try."""
    agent_api.model.replies = [
        *[render(FAILING)] * 4,
        ("text", "It failed three times."),
        render(FAILING),
        ("text", "It failed again."),
    ]
    thread = await open_thread(agent_api)

    await send(agent_api, thread["id"], "Draft the proposal")
    stopped = _last_tool_result(agent_api.model.requests[4])
    made = await agent_api.http.get(f"/workspaces/{agent_api.workspace_id}/artifacts")
    await send(agent_api, thread["id"], "Try once more")

    assert "no more renders run until the user's next message" in stopped
    assert len(made.json()) == 3
    assert "ValueError: the pricing table is empty" in _last_tool_result(
        agent_api.model.requests[6]
    )


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
        "created": True,
    }
