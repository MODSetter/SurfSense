"""SurfSense's tool endpoint driven in-process, as opencode's MCP client reaches it."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.main import create_app
from modules.chat.models import ChatThread
from modules.source_scope.schemas import SourceScope
from shared.config import get_storage_settings
from shared.db import create_session_factory


@dataclass
class ToolEndpoint:
    """The app as opencode's MCP client reaches it, with the key it was launched with.

    A call without a `thread` comes from the workspace's first agent thread,
    which stores no scope and so uses every source.
    """

    client: AsyncClient
    launch_key: str
    sessions: sessionmaker[Session]
    _default_threads: dict[int, int] = field(default_factory=dict)

    async def workspace(self) -> int:
        """A new workspace, made the way the app makes one."""
        reply = await self.client.post("/workspaces", json={"name": "Research"})
        reply.raise_for_status()
        return reply.json()["id"]

    def thread(
        self,
        workspace_id: int,
        scope: SourceScope | None = None,
        *,
        agent: bool = True,
    ) -> int:
        """A thread as opening one leaves it, its ticks stored; `agent` False is a chat's."""
        with self.sessions() as session:
            thread = ChatThread(
                workspace_id=workspace_id,
                title="New chat",
                opencode_session_id="ses_test" if agent else None,
                source_scope=None if scope is None else scope.model_dump(),
            )
            session.add(thread)
            session.commit()
            return thread.id

    def default_thread(self, workspace_id: int) -> int:
        if workspace_id not in self._default_threads:
            self._default_threads[workspace_id] = self.thread(workspace_id)
        return self._default_threads[workspace_id]

    def folder(self, workspace_id: int, thread_id: int | None = None) -> Path:
        """The folder a thread's tools write figures, pages and previews to."""
        if thread_id is None:
            thread_id = self.default_thread(workspace_id)
        return get_storage_settings().thread_working_dir(workspace_id, thread_id)

    async def post(
        self,
        workspace_id: int,
        message: dict[str, Any],
        *,
        thread: int | None = None,
        **headers: str,
    ) -> Response:
        """One JSON-RPC message, sent as opencode's client sends it to a thread's address."""
        if thread is None:
            thread = self.default_thread(workspace_id)
        return await self.client.post(
            f"/agent/tools/workspaces/{workspace_id}/threads/{thread}",
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
        thread: int | None = None,
    ) -> dict[str, Any]:
        """A request's JSON-RPC reply."""
        message = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            message["params"] = params
        reply = await self.post(workspace_id, message, thread=thread)
        assert reply.status_code == 200, reply.text
        return reply.json()

    async def call(
        self,
        workspace_id: int,
        name: str,
        arguments: dict[str, Any],
        *,
        thread: int | None = None,
    ) -> tuple[str, bool]:
        """One tool call's text and whether it is an error, as the model reads it."""
        reply = await self.request(
            workspace_id,
            "tools/call",
            {"name": name, "arguments": arguments},
            thread=thread,
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
        yield ToolEndpoint(
            client, app.state.agent_launch_key, app.state.session_factory
        )
