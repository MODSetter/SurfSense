"""Telling opencode where a thread's tools are, as opencode receives it."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from modules.agent.opencode_client import OpencodeClient
from modules.agent.previews.document_previews import WORD_SNAPSHOT_SECONDS
from modules.agent.tool_endpoint import render_document
from modules.agent.tool_endpoint.registration import (
    TOOL_CALL_SECONDS,
    register_thread_tools,
)

pytestmark = pytest.mark.integration


_ADDED = "/api/experimental/mcp/"


class _Opencode(BaseHTTPRequestHandler):
    """Answers opencode 2.x's routes for adding, connecting and listing an MCP server,
    keeping each server it was given, by name, with its config and folder."""

    def do_PUT(self) -> None:
        sent = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        parts = urlsplit(self.path)
        sent["name"] = parts.path.removeprefix(_ADDED)
        self.server.sent.append(sent)  # type: ignore[attr-defined]
        self.server.queries.append(parse_qs(parts.query))  # type: ignore[attr-defined]
        self._answer(204)

    def do_POST(self) -> None:
        self._answer(204)  # the connect, which answers once it has

    def do_GET(self) -> None:
        names = [sent["name"] for sent in self.server.sent]  # type: ignore[attr-defined]
        held = [{"name": n, "status": {"status": "connected"}} for n in names]
        self._answer(200, {"data": held})

    def _answer(self, status: int, body: object = None) -> None:
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def opencode() -> Iterator[ThreadingHTTPServer]:
    """A stand-in for opencode's server, on a real port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Opencode)
    server.sent = []  # type: ignore[attr-defined]
    server.queries = []  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


async def test_a_tool_call_may_run_as_long_as_a_render_waits(
    opencode: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Unless told otherwise, opencode allows a tool call 12 hours, which no progress shortens."""
    async with OpencodeClient(
        f"http://127.0.0.1:{opencode.server_port}", "pw"
    ) as client:
        await register_thread_tools(client, tmp_path, 7, 12, "launch-key")

    (sent,) = opencode.sent  # type: ignore[attr-defined]
    config = sent["config"]
    assert (sent["name"], config["type"]) == ("surfsense", "remote")
    assert config["timeout"]["execution"] == TOOL_CALL_SECONDS * 1000  # in ms


async def test_each_turn_registers_its_threads_address_in_its_threads_folder(
    opencode: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """A tool call names no thread, so the address and the instance it is given to do."""
    first, second = tmp_path / "threads" / "12", tmp_path / "threads" / "13"
    async with OpencodeClient(
        f"http://127.0.0.1:{opencode.server_port}", "pw"
    ) as client:
        await register_thread_tools(client, first, 7, 12, "launch-key")
        await register_thread_tools(client, second, 7, 13, "launch-key")

    registered = [
        (query["location[directory]"][0], urlsplit(sent["config"]["url"]).path)
        for query, sent in zip(
            opencode.queries,  # type: ignore[attr-defined]
            opencode.sent,  # type: ignore[attr-defined]
            strict=True,
        )
    ]
    assert registered == [
        (str(first), "/agent/tools/workspaces/7/threads/12"),
        (str(second), "/agent/tools/workspaces/7/threads/13"),
    ]


def test_a_render_answers_before_opencode_gives_up_on_the_call() -> None:
    """The longest wait for the job and the longest Word preview fit in the call.

    What is left past them is room for SQLite's busy waits and drawing the pages,
    so a version that is made is never reported to the model as a timeout.
    """
    longest = render_document.WAIT_SECONDS + WORD_SNAPSHOT_SECONDS

    assert longest <= render_document.CALL_SECONDS < TOOL_CALL_SECONDS


async def test_tools_held_connected_as_given_are_not_given_again(
    opencode: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Giving them again makes opencode connect to the API anew, a handshake each turn."""
    async with OpencodeClient(
        f"http://127.0.0.1:{opencode.server_port}", "pw"
    ) as client:
        first = await register_thread_tools(client, tmp_path, 7, 12, "launch-key")
        held = await register_thread_tools(
            client, tmp_path, 7, 12, "launch-key", "connected"
        )
        failed = await register_thread_tools(
            client, tmp_path, 7, 12, "launch-key", "failed"
        )
        # A new API process has a new key, which the held connection does not carry.
        restarted = await register_thread_tools(
            client, tmp_path, 7, 12, "new-key", "connected"
        )

    assert (first, held, failed, restarted) == (True, False, True, True)
    assert len(opencode.sent) == 3  # type: ignore[attr-defined]
