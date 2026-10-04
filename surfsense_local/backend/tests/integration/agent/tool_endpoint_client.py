"""SurfSense's tool endpoint driven in-process, as opencode's MCP client reaches it."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine

from api.main import create_app
from shared.db import create_session_factory


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
        self, workspace_id: int, message: dict[str, Any], **headers: str
    ) -> Response:
        """One JSON-RPC message, sent with the headers opencode's client sends."""
        return await self.client.post(
            f"/agent/tools/workspaces/{workspace_id}",
            json=message,
            headers={
                "Authorization": f"Bearer {self.launch_key}",
                "Accept": "application/json, text/event-stream",
                **headers,
            },
        )

    async def request(
        self, workspace_id: int, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """A request's JSON-RPC reply."""
        message = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            message["params"] = params
        reply = await self.post(workspace_id, message)
        assert reply.status_code == 200, reply.text
        return reply.json()

    async def call(
        self, workspace_id: int, name: str, arguments: dict[str, Any]
    ) -> tuple[str, bool]:
        """One tool call's text and whether it is an error, as the model reads it."""
        reply = await self.request(
            workspace_id, "tools/call", {"name": name, "arguments": arguments}
        )
        (content,) = reply["result"]["content"]
        return content["text"], reply["result"]["isError"]


@asynccontextmanager
async def endpoint_over(engine: Engine) -> AsyncIterator[ToolEndpoint]:
    """The tool endpoint of a fresh app on `engine`'s database."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ToolEndpoint(client, app.state.agent_launch_key)
