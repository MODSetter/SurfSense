"""The client the backend drives opencode with, against the real staged opencode."""

import asyncio
import contextlib
import json
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
from tests.integration.agent.opencode_harness import (
    MODEL,
    RunningOpencode,
    ScriptedModel,
)

pytestmark = pytest.mark.integration


class EventLog:
    """Everything one folder's event stream has sent, read in the background."""

    def __init__(self, client: OpencodeClient, directory: Path) -> None:
        self.seen: list[Event] = []
        self._client = client
        self._directory = directory
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
        async for event in self._client.events(self._directory):
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
    """The folder a turn works in, laid out as a workspace's is: `…/<id>/agent`."""
    work = tmp_path / "workspaces" / "1" / "agent"
    (work / "outputs").mkdir(parents=True)
    return work


def idle(session_id: str) -> Callable[[Event], bool]:
    """Matches the end of every turn in one session."""
    return lambda event: (
        event.type == "session.idle" and event.properties["sessionID"] == session_id
    )


def tool_part(status: str) -> Callable[[Event], bool]:
    """Matches a shell call reaching `status`."""
    return lambda event: (
        event.type == "message.part.updated"
        and event.properties["part"].get("type") == "tool"
        and event.properties["part"]["state"]["status"] == status
    )


async def test_it_speaks_only_to_the_pinned_opencode(client: OpencodeClient) -> None:
    """The staged build is the release the client was written against."""
    assert await client.version() == OPENCODE_VERSION == "1.18.34"
    await client.require_pinned_version()


async def test_it_refuses_an_opencode_of_another_version() -> None:
    """The backend was written against one release's API; any other could mislead it."""

    class Newer(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps({"healthy": True, "version": "1.19.0"}).encode()
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
            with pytest.raises(OpencodeVersionError, match=r"1\.19\.0"):
                await client.require_pinned_version()
    finally:
        server.shutdown()
        server.server_close()


async def test_a_turn_streams_its_reply_and_ends_idle(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """A turn returns at once; its words and its end arrive as events."""
    scripted_model.replies = [("text", "Revenue rose in Q3.")]
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "What happened in Q3?", model=MODEL)
        await log.until(idle(session_id))

    deltas = [e.properties["delta"] for e in log.seen if e.type == "message.part.delta"]
    assert "".join(deltas) == "Revenue rose in Q3."
    # The session was named by SurfSense, so opencode asked the model nothing else.
    assert len(scripted_model.requests) == 1


async def test_a_shell_command_asks_first_and_runs_once_allowed(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """No command runs before the user says yes (ADR 0028)."""
    scripted_model.replies = [("bash", "echo allowed-run"), ("text", "It printed.")]
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "Run it", model=MODEL)
        asked = await log.until(lambda e: e.type == "permission.asked")
        assert asked.properties["permission"] == "bash"
        assert asked.properties["metadata"]["command"] == "echo allowed-run"

        await client.reply(folder, asked.properties["id"], "once")
        done = await log.until(tool_part("completed"))
        await log.until(idle(session_id))

    assert done.properties["part"]["state"]["output"].strip() == "allowed-run"


async def test_rejecting_a_shell_command_stops_it(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """A no ends the call and the turn, and nothing runs."""
    scripted_model.replies = [("bash", "echo never-run")]
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "Run it", model=MODEL)
        asked = await log.until(lambda e: e.type == "permission.asked")

        await client.reply(folder, asked.properties["id"], "reject")
        await log.until(tool_part("error"))
        await log.until(idle(session_id))

    assert not any(tool_part("completed")(e) for e in log.seen)


async def test_stopping_ends_a_running_turn(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """Stop must work while the model is still answering."""
    scripted_model.replies = [("stall", "Thinking about")]
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "Take your time", model=MODEL)
        await log.until(lambda e: e.type == "message.part.delta")

        await client.abort(folder, session_id)
        await log.until(idle(session_id), timeout=10)


async def test_a_deleted_session_is_gone(client: OpencodeClient, folder: Path) -> None:
    """Deleting a thread must not leave its conversation behind in opencode."""
    session_id = await client.create_session(folder, "Thread 1")

    await client.delete_session(folder, session_id)

    assert session_id not in await client.session_ids(folder)


def write_call(path: str, content: str) -> tuple[str, str]:
    """A scripted `write` tool call, as a model would make it."""
    return (
        "call",
        json.dumps(
            {"name": "write", "arguments": {"filePath": path, "content": content}}
        ),
    )


async def test_the_agent_writes_what_it_produces_to_outputs(
    client: OpencodeClient, folder: Path, scripted_model: ScriptedModel
) -> None:
    """The output folder is the agent's; a deliverable it cannot write is no deliverable."""
    scripted_model.replies = [
        write_call("outputs/summary.md", "Revenue rose."),
        ("text", "Wrote it."),
    ]
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "Summarise", model=MODEL)
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
    session_id = await client.create_session(folder, "Thread 1")

    async with EventLog(client, folder) as log:
        await client.send_turn(folder, session_id, "Rewrite the plan", model=MODEL)
        await log.until(tool_part("error"))
        await log.until(idle(session_id))

    assert not (folder / "sources" / "Plan [1].md").exists()
