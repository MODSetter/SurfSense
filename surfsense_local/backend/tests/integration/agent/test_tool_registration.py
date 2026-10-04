"""Telling opencode where a workspace's tools are, as opencode receives it."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from modules.agent.opencode_client import OpencodeClient
from modules.agent.previews.document_previews import WORD_SNAPSHOT_SECONDS
from modules.agent.tool_endpoint import render_document
from modules.agent.tool_endpoint.registration import (
    TOOL_CALL_SECONDS,
    register_workspace_tools,
)

pytestmark = pytest.mark.integration


class _Opencode(BaseHTTPRequestHandler):
    """Answers `POST /mcp` as opencode does, keeping each body it was sent."""

    def do_POST(self) -> None:
        sent = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.sent.append(sent)  # type: ignore[attr-defined]
        body = json.dumps({sent["name"]: {"status": "connected"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def opencode() -> Iterator[ThreadingHTTPServer]:
    """A stand-in for opencode's server, on a real port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Opencode)
    server.sent = []  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


async def test_a_tool_call_may_run_as_long_as_a_render_waits(
    opencode: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """Unless told otherwise, opencode leaves a tool call to its MCP SDK's 60 s limit."""
    async with OpencodeClient(
        f"http://127.0.0.1:{opencode.server_port}", "pw"
    ) as client:
        await register_workspace_tools(client, tmp_path, 7, "launch-key")

    (sent,) = opencode.sent  # type: ignore[attr-defined]
    config = sent["config"]
    assert (sent["name"], config["type"]) == ("surfsense", "remote")
    assert config["url"].endswith("/agent/tools/workspaces/7")
    assert config["timeout"] == TOOL_CALL_SECONDS * 1000  # in milliseconds


def test_a_render_answers_before_opencode_gives_up_on_the_call() -> None:
    """The longest wait for the job and the longest Word preview fit in the call.

    What is left past them is room for SQLite's busy waits and drawing the pages,
    so a version that is made is never reported to the model as a timeout.
    """
    longest = render_document.WAIT_SECONDS + WORD_SNAPSHOT_SECONDS

    assert longest <= render_document.CALL_SECONDS < TOOL_CALL_SECONDS
