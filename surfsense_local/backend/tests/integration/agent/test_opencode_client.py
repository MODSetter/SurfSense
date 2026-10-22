"""The client the backend drives opencode with, against the real staged opencode."""

import asyncio
import contextlib
import json
import shutil
import threading
from collections.abc import AsyncIterator, Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import pytest_asyncio

from modules.agent.opencode_client import (
    OPENCODE_VERSION,
    Event,
    OpencodeClient,
    OpencodeVersionError,
)
from modules.agent.opencode_config import skills_folder
from tests.integration.agent.opencode_harness import (
    MODEL,
    RunningOpencode,
    ScriptedModel,
)

pytestmark = pytest.mark.integration


class EventLog:
    """Everything opencode's event stream has sent, read in the background."""

    def __init__(self, client: OpencodeClient) -> None:
        self.seen: list[Event] = []
        self._client = client
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> "EventLog":
        self._task = asyncio.create_task(self._read())
        await self.until(lambda event: event.type == "server.connected")
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._task is not None
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _read(self) -> None:
        """Keep every event, in order."""
        async for event in self._client.events():
            self.seen.append(event)

    async def until(
        self, wanted: Callable[[Event], bool], timeout: float = 30.0
    ) -> Event:
        """The first event that matches, waiting for it if it has not come yet."""
        async with asyncio.timeout(timeout):
            while True:
                for event in self.seen:
                    if wanted(event):
                        return event
                await asyncio.sleep(0.05)


@pytest_asyncio.fixture(loop_scope="function")
async def client(opencode: RunningOpencode) -> AsyncIterator[OpencodeClient]:
    """The backend's client for the opencode this test started, on the test's own loop."""
    async with OpencodeClient(opencode.url, opencode.password) as client:
        yield client


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """The folder a thread works in, laid out as one is: `…/<id>/agent/threads/<thread>`."""
    work = tmp_path / "workspaces" / "1" / "agent" / "threads" / "7"
    (work / "outputs").mkdir(parents=True)
    return work


_ENDED = (
    "session.execution.succeeded",
    "session.execution.failed",
    "session.execution.interrupted",
)


def idle(session_id: str) -> Callable[[Event], bool]:
    """Matches the end of every turn in one session, however it ended."""
    return lambda event: event.type in _ENDED and event.data["sessionID"] == session_id


def tool_part(status: str) -> Callable[[Event], bool]:
    """Matches a tool call reaching `status`: `completed` or `error`."""
    kind = {"completed": "session.tool.success", "error": "session.tool.failed"}
    return lambda event: event.type == kind[status]


async def test_it_speaks_only_to_the_pinned_opencode(client: OpencodeClient) -> None:
    """The staged build is the release the client was written against."""
    assert await client.version() == OPENCODE_VERSION == "2.1.2"
    await client.require_pinned_version()


async def test_it_refuses_an_opencode_of_another_version() -> None:
    """The backend was written against one release's API; any other could mislead it."""

    class Newer(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"version": "2.2.0", "pid": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Keep the request log out of the test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Newer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        async with OpencodeClient(
            f"http://127.0.0.1:{server.server_port}", "pw"
        ) as client:
            with pytest.raises(OpencodeVersionError, match=r"2\.2\.0"):
                await client.require_pinned_version()
    finally:
        server.shutdown()
        server.server_close()


async def test_a_turn_streams_its_reply_and_ends_idle(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """A turn returns at once; its words and its end arrive as events."""
    scripted_model.replies = [("text", "Revenue rose in Q3.")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "What happened in Q3?", model=MODEL)
        await log.until(idle(session_id))

    deltas = [e.data["delta"] for e in log.seen if e.type == "session.text.delta"]
    assert "".join(deltas) == "Revenue rose in Q3."
    # The session was named by SurfSense, so opencode asked the model nothing else.
    assert len(scripted_model.requests) == 1


# A plugin tool the user must allow, as SurfSense's session rules ask about one;
# a built-in tool stands in for it.
GLOB = ("call", json.dumps({"name": "glob", "arguments": {"pattern": "*.md"}}))
ASK_GLOB = [{"permission": "glob", "pattern": "*", "action": "ask"}]


def asked() -> Callable[[Event], bool]:
    """Matches an approval opencode waits on."""
    return lambda event: event.type == "permission.asked"


async def test_the_agent_has_no_shell(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """No shell is offered, and a call to one runs nothing and asks nothing (ADR 0039)."""
    scripted_model.replies = [("bash", "echo ran > outputs/ran.txt"), ("text", "No.")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Run it", model=MODEL)
        await log.until(idle(session_id))

    offered = [tool["function"]["name"] for tool in scripted_model.requests[0]["tools"]]
    assert "bash" not in offered
    assert "shell" not in offered
    assert not any(asked()(event) for event in log.seen)
    assert not (folder / "outputs" / "ran.txt").exists()


async def test_an_approval_waits_for_the_answer_and_goes_on_once_allowed(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """Nothing opencode asks about runs before the user's answer reaches it."""
    scripted_model.replies = [GLOB, ("text", "Listed.")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)
    await client.set_session_rules(session_id, ASK_GLOB)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "List them", model=MODEL)
        request = await log.until(asked())
        assert request.data["action"] == "glob"
        # The tool call it holds back, so the thread asks on that step.
        assert request.data["source"]["id"] == "call_1"
        assert not any(tool_part("completed")(e) for e in log.seen)

        await client.reply(session_id, request.data["id"], "once")
        await log.until(tool_part("completed"))
        await log.until(idle(session_id))


async def test_rejecting_an_approval_stops_the_call(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """A no fails the call it was asked about, and the turn ends."""
    scripted_model.replies = [GLOB]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)
    await client.set_session_rules(session_id, ASK_GLOB)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "List them", model=MODEL)
        request = await log.until(asked())

        await client.reply(session_id, request.data["id"], "reject")
        await log.until(tool_part("error"))
        await log.until(idle(session_id))


async def test_stopping_ends_a_running_turn(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """Stop must work while the model is still answering."""
    scripted_model.replies = [("stall", "Thinking about")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Take your time", model=MODEL)
        await log.until(lambda e: e.type == "session.text.delta")
        assert await client.status(session_id) == "running"

        await client.abort(session_id)
        await log.until(idle(session_id), timeout=10)
    assert await client.status(session_id) == "idle"


async def test_a_deleted_session_is_gone(client: OpencodeClient, folder: Path) -> None:
    """Deleting a thread must not leave its conversation behind in opencode."""
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    await client.delete_session(session_id)

    assert session_id not in await client.session_ids(folder)


async def test_a_session_says_the_folder_it_was_made_in(
    client: OpencodeClient, folder: Path
) -> None:
    """A session cannot move; whether it is a thread's own tells a legacy thread apart."""
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    assert Path(await client.session_directory(session_id)) == folder


async def test_a_disposed_folder_still_reads_its_sessions_back(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """Disposing frees the folder's instance; the next call starts another from the stored session."""
    scripted_model.replies = [("text", "Revenue rose.")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)
    async with EventLog(client) as log:
        await client.send_turn(session_id, "Q3?", model=MODEL)
        await log.until(idle(session_id))

    await client.dispose_instance(folder)

    messages = await client.messages(session_id)
    assert [m["type"] for m in messages] == ["user", "assistant", "idle"]


async def test_notes_go_before_the_users_words_as_messages_of_their_own(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """The model reads SurfSense's notes, and the session keeps them apart from the user's words."""
    scripted_model.replies = [("text", "Done.")]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Q3?", model=MODEL, notes=["A note."])
        await log.until(idle(session_id))

    messages = await client.messages(session_id)
    assert [(m["type"], m.get("text")) for m in messages[:2]] == [
        ("synthetic", "A note."),
        ("user", "Q3?"),
    ]
    sent = [m.get("content") for m in scripted_model.requests[0]["messages"][1:]]
    assert sent == ["A note.", "Q3?"]


async def test_a_long_session_reads_back_whole(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """opencode pages a session's messages; a thread shows every turn."""
    turns = 70  # three messages each, past a page of 200
    scripted_model.replies = [("text", "Ok.")] * turns
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)
    async with EventLog(client) as log:
        for n in range(turns):
            log.seen.clear()
            await client.send_turn(session_id, f"Turn {n}", model=MODEL)
            await log.until(idle(session_id))

    messages = await client.messages(session_id)
    users = [m["text"] for m in messages if m["type"] == "user"]
    assert users == [f"Turn {n}" for n in range(turns)]


def write_call(path: str, content: str) -> tuple[str, str]:
    """A scripted `write` tool call, as a model would make it."""
    return (
        "call",
        json.dumps({"name": "write", "arguments": {"path": path, "content": content}}),
    )


async def test_the_agent_writes_what_it_produces_to_outputs(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """The output folder is the agent's; a deliverable it cannot write is no deliverable."""
    scripted_model.replies = [
        write_call("outputs/summary.md", "Revenue rose."),
        ("text", "Wrote it."),
    ]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Summarise", model=MODEL)
        await log.until(idle(session_id))

    assert (folder / "outputs" / "summary.md").read_text() == "Revenue rose."


async def test_the_agent_cannot_change_its_sources(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """The sources are SurfSense's copy of the user's documents, rebuilt from the library."""
    (folder / "sources").mkdir()
    scripted_model.replies = [
        write_call("sources/Plan [1].md", "Rewritten."),
        ("text", "Done."),
    ]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Rewrite the plan", model=MODEL)
        await log.until(tool_part("error"))
        await log.until(idle(session_id))

    assert not (folder / "sources" / "Plan [1].md").exists()


async def test_the_agent_may_read_the_long_output_opencode_set_aside(
    client: OpencodeClient,
    folder: Path,
    scripted_model: ScriptedModel,
    opencode: RunningOpencode,
) -> None:
    """opencode cuts a long tool result and points at the rest in its data folder,
    outside the agent's; every other folder outside stays shut."""
    set_aside = opencode.agent_dir / "opencode" / "data" / "opencode" / "tool-output"
    set_aside.mkdir(parents=True)
    (set_aside / "tool_1").write_text("The rest of the output.")
    elsewhere = folder.parent / "elsewhere.txt"
    elsewhere.write_text("Not the agent's.")
    scripted_model.replies = [
        read_call(str(set_aside / "tool_1")),
        read_call(str(elsewhere)),
        ("text", "Read."),
    ]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)

    async with EventLog(client) as log:
        await client.send_turn(session_id, "Read on", model=MODEL)
        await log.until(idle(session_id))

    finished = [
        e for e in log.seen if tool_part("completed")(e) or tool_part("error")(e)
    ]
    assert [e.type for e in finished] == ["session.tool.success", "session.tool.failed"]
    assert "The rest of the output." in finished[0].data["content"][0]["text"]


def read_call(path: str) -> tuple[str, str]:
    """A scripted `read` tool call."""
    return ("call", json.dumps({"name": "read", "arguments": {"path": path}}))


_OUTPUTS_OF_A_THREAD = Path("agent", "threads", "7", "outputs")

# Paths whose name holds a thread's `outputs/` but which opencode loads as
# configuration, SurfSense rebuilds as sources, every workspace shares, or
# another thread owns.
_NOT_OUTPUTS = {
    "skills": lambda folder, opencode: (
        skills_folder().resolve() / "zzz-probe" / _OUTPUTS_OF_A_THREAD / "SKILL.md"
    ),
    "agent definitions": lambda folder, opencode: (
        folder / ".opencode" / _OUTPUTS_OF_A_THREAD / "x.md"
    ),
    "sources": lambda folder, opencode: (
        folder / "sources" / _OUTPUTS_OF_A_THREAD / "x.md"
    ),
    "a mirrored folder named outputs": lambda folder, opencode: (
        folder / "sources" / "Library" / "outputs" / "x.md"
    ),
    "long tool output": lambda folder, opencode: (
        opencode.agent_dir
        / "opencode"
        / "data"
        / "opencode"
        / "tool-output"
        / _OUTPUTS_OF_A_THREAD
        / "x.md"
    ),
    "another thread's outputs": lambda folder, opencode: (
        folder.parent / "8" / "outputs" / "x.md"
    ),
    "an instruction file": lambda folder, opencode: folder / "outputs" / "AGENTS.md",
}


@pytest.mark.parametrize("where", list(_NOT_OUTPUTS))
async def test_a_path_that_only_names_outputs_is_refused(
    client: OpencodeClient,
    folder: Path,
    scripted_model: ScriptedModel,
    opencode: RunningOpencode,
    where: str,
) -> None:
    """Only the thread's own outputs folder is writable, however a path spells it."""
    target = _NOT_OUTPUTS[where](folder, opencode)
    scripted_model.replies = [
        write_call(str(target), "---\nname: surfsense\n---\nPlanted."),
        ("text", "Done."),
    ]
    session_id = await client.create_session(folder, "Thread 1", model=MODEL)
    try:
        async with EventLog(client) as log:
            await client.send_turn(session_id, "Save it", model=MODEL)
            await log.until(idle(session_id))

        assert any(tool_part("error")(event) for event in log.seen)
        assert not any(asked()(event) for event in log.seen)
        assert not target.exists()
    finally:
        if where == "skills":
            shutil.rmtree(skills_folder().resolve() / "zzz-probe", ignore_errors=True)
