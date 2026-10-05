"""SurfSense's tool endpoint driven in-process, as opencode's MCP client reaches it."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine

from api.main import create_app
from modules.agent.tool_endpoint.turn_scope import remember_turn_scope
from shared.db import create_session_factory

# A call made as a turn with no `document_ids` makes it: over the whole workspace.
WHOLE_WORKSPACE = object()


@dataclass
class ToolEndpoint:
    """The app as opencode's MCP client reaches it, with the key it was launched with."""

    client: AsyncClient
    launch_key: str

    async def workspace(self) -> int:
        """A new workspace, made the way the app makes one."""
        reply = await self.client.post("/workspaces", json={"name": "Research"})
        reply.raise_for_status()
        return reply.json()["id"]

    async def post(
        self,
        workspace_id: int,
        message: dict[str, Any],
        *,
        token: object = WHOLE_WORKSPACE,
        **headers: str,
    ) -> Response:
        """One JSON-RPC message, sent as opencode's client sends it to a turn's address.

        `token` is the turn's scope token, None for an address without one.
        """
        if token is WHOLE_WORKSPACE:
            token = remember_turn_scope(workspace_id, None)
        return await self.client.post(
            f"/agent/tools/workspaces/{workspace_id}",
            params={} if token is None else {"scope": token},
            json=message,
            headers={
                "Authorization": f"Bearer {self.launch_key}",
                "Accept": "application/json, text/event-stream",
                **headers,
            },
        )

    async def request(
        self,
        workspace_id: int,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        token: object = WHOLE_WORKSPACE,
    ) -> dict[str, Any]:
        """A request's JSON-RPC reply."""
        message = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            message["params"] = params
        reply = await self.post(workspace_id, message, token=token)
        assert reply.status_code == 200, reply.text
        return reply.json()

    async def call(
        self,
        workspace_id: int,
        name: str,
        arguments: dict[str, Any],
        *,
        token: object = WHOLE_WORKSPACE,
    ) -> tuple[str, bool]:
        """One tool call's text and whether it is an error, as the model reads it."""
        text, _, is_error = await self.call_content(
            workspace_id, name, arguments, token=token
        )
        return text, is_error

    async def call_content(
        self,
        workspace_id: int,
        name: str,
        arguments: dict[str, Any],
        *,
        token: object = WHOLE_WORKSPACE,
    ) -> tuple[str, list[dict[str, Any]], bool]:
        """One tool call's text, the image items after it, and whether it is an error.

        opencode joins text items with blank lines and the render's first line
        names its version, so a result is one text item, then only images.
        """
        reply = await self.request(
            workspace_id,
            "tools/call",
            {"name": name, "arguments": arguments},
            token=token,
        )
        first, *images = reply["result"]["content"]
        assert set(first) == {"type", "text"} and first["type"] == "text", first
        for image in images:
            assert set(image) == {"type", "data", "mimeType"}, set(image)
            assert image["type"] == "image", image["type"]
        return first["text"], images, reply["result"]["isError"]


@asynccontextmanager
async def endpoint_over(engine: Engine) -> AsyncIterator[ToolEndpoint]:
    """The tool endpoint of a fresh app on `engine`'s database."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ToolEndpoint(client, app.state.agent_launch_key)
