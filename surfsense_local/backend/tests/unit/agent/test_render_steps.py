"""A render step in the thread: it links the document only once that version is ready."""

from typing import Any

import pytest

from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.steps import step_of
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.opencode_client import Event

pytestmark = pytest.mark.unit

SESSION = "ses_1"
READY_OUTPUT = (
    "Rendered artifact 40, version 2: Client proposal\n"
    "A Word document of 3 paragraphs. Its text begins:"
)


def _tool_part(
    tool: str,
    status: str,
    output: str | None = None,
    error: str | None = None,
    files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A tool call as opencode stores it, in an assistant message's content."""
    state: dict[str, Any] = {"status": status, "input": {"title": "Client proposal"}}
    content = ([{"type": "text", "text": output}] if output is not None else []) + (
        files or []
    )
    if content:
        state["content"] = content
    if error is not None:
        state["error"] = {"type": "tool.execution", "message": error}
    return {"type": "tool", "id": "call_1", "name": tool, "state": state}


def _steps(*parts: dict[str, Any]) -> list[dict[str, Any]]:
    """The agent-step frame each call's last event makes, as the stream sends them."""
    turn = TurnFrames(SESSION)

    def frames(kind: str, **data: Any) -> list[dict[str, Any]]:
        return turn.frames(Event(type=kind, data={"sessionID": SESSION, **data}))

    frames("session.inbox.enqueued", inboxID="msg_u", item={"type": "user"})
    shown = []
    for part in parts:
        state = part["state"]
        call = {"assistantMessageID": "msg_a", "id": part["id"]}
        frames("session.tool.input.started", **call, name=part["name"])
        called = frames("session.tool.called", **call, input=state["input"])
        if state["status"] == "running":
            shown += called
        elif state["status"] == "completed":
            shown += frames("session.tool.success", **call, content=state["content"])
        else:
            shown += frames("session.tool.failed", **call, error=state["error"])
    return shown


def _messages(*parts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": "msg_u", "type": "user", "text": "Write it"},
        {"id": "msg_a", "type": "assistant", "content": list(parts)},
    ]


def test_a_ready_render_links_the_version_it_made() -> None:
    """The thread opens that version in Studio, and says which version it is."""
    running, done = _steps(
        _tool_part("surfsense_render_document", "running"),
        _tool_part("surfsense_render_document", "completed", output=READY_OUTPUT),
    )

    assert running["artifact"] is None
    assert done["artifact"] == {"id": 40, "title": "Client proposal", "version": 2}


def test_a_failed_render_links_nothing() -> None:
    """The failed version exists, but there is no document to open."""
    (failed,) = _steps(
        _tool_part(
            "surfsense_render_document",
            "error",
            error='Version 2 of "Client proposal" (artifact 41) failed:\nValueError',
        )
    )

    assert failed["artifact"] is None


def test_a_render_still_running_at_the_limit_links_nothing() -> None:
    """The call returned before the version was ready."""
    (waiting,) = _steps(
        _tool_part(
            "surfsense_render_document",
            "completed",
            output='Version 1 of "Client proposal" (artifact 40) is still being made',
        )
    )

    assert waiting["artifact"] is None


def test_other_steps_carry_no_artifact() -> None:
    """Only a render makes a document version."""
    (read,) = _steps(_tool_part("read", "completed", output=READY_OUTPUT))

    assert "artifact" not in read


def test_a_stored_reply_links_its_render_as_the_stream_did() -> None:
    """Reopening the thread shows the same "Updated … to v2" the stream showed."""
    messages = _messages(
        _tool_part("surfsense_render_document", "completed", output=READY_OUTPUT)
    )

    reply = turn_reply(messages, "msg_u", [])

    (step,) = reply["content"]["steps"]
    assert step["artifact"] == {"id": 40, "title": "Client proposal", "version": 2}


def test_a_steps_attachments_never_reach_the_thread() -> None:
    """opencode keeps a render's page images in its result; the thread carries none of their bytes."""
    data = "QUJD" * 2000
    pages = [
        {"type": "file", "mime": "image/jpeg", "uri": f"data:image/jpeg;base64,{data}"}
    ]
    part = _tool_part(
        "surfsense_render_document", "completed", output=READY_OUTPUT, files=pages
    )
    messages = _messages(part)

    (streamed,) = _steps(part)
    reply = turn_reply(messages, "msg_u", [])

    for shown in (step_of(part), streamed, reply):
        assert "base64" not in str(shown)
        assert data not in str(shown)
    (stored,) = reply["content"]["steps"]
    for step in (streamed, stored):
        assert step["artifact"] == {"id": 40, "title": "Client proposal", "version": 2}


def test_a_finished_conversion_links_the_pdf_it_made() -> None:
    """The thread opens the new PDF in Studio, as it opens a rendered version."""
    step = step_of(
        _tool_part(
            "surfsense_convert_document",
            "completed",
            output=(
                "Rendered artifact 41, version 1: Client proposal\n"
                "A PDF of 3 pages, converted by LibreOffice 26.8.1 from artifact 40."
            ),
        )
    )

    assert step["artifact"] == {"id": 41, "title": "Client proposal", "version": 1}


def test_a_ready_revise_links_the_revised_copy_it_made() -> None:
    """A revised copy's version opens from the thread as a render's does."""
    output = (
        "Rendered artifact 51, version 2: MSA_Acme (revised)\n"
        "Revised copy of source 42 (MSA_Acme.docx), version 2 from version 1."
    )

    step = step_of(_tool_part("surfsense_revise_document", "completed", output=output))

    assert step["artifact"] == {"id": 51, "title": "MSA_Acme (revised)", "version": 2}


def test_a_saved_page_links_the_version_it_made() -> None:
    """A page the agent saved opens in Studio from its step, as a render does."""
    (done,) = _steps(
        _tool_part(
            "surfsense_save_page",
            "completed",
            output="Rendered artifact 52, version 2: Q3 revenue\nA web page of 4 KB.",
        )
    )

    assert done["artifact"] == {"id": 52, "title": "Q3 revenue", "version": 2}
