from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal, Self

import httpx

from modules.agent.opencode_client.events import read_events
from modules.agent.opencode_client.payloads import Event
from modules.agent.opencode_config import AGENT, PROVIDER

# The release electron/scripts/opencode/pins.mjs stages; its HTTP API is unversioned.
OPENCODE_VERSION = "1.18.34"

# Every call but the event stream answers at once; a server that does not was
# seen to accept a connection and never reply while starting.
_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
_HEALTH_TIMEOUT = httpx.Timeout(3.0, connect=2.0)


class OpencodeVersionError(RuntimeError):
    """The opencode that answered is not the release SurfSense was written against."""


class OpencodeClient:
    """The backend's calls to opencode, each scoped to the folder a workspace works in."""

    def __init__(self, url: str, password: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=url, auth=("opencode", password), timeout=_TIMEOUT
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Release the connection pool."""
        await self._http.aclose()

    async def version(self) -> str:
        """The release the running server reports."""
        reply = await self._http.get("/global/health", timeout=_HEALTH_TIMEOUT)
        reply.raise_for_status()
        return reply.json()["version"]

    async def require_pinned_version(self) -> None:
        """Refuse to go on with any opencode but the pinned one."""
        running = await self.version()
        if running != OPENCODE_VERSION:
            raise OpencodeVersionError(
                f"opencode {running} is running; SurfSense speaks {OPENCODE_VERSION}"
            )

    async def config(self) -> dict[str, Any]:
        """The configuration the running server loaded."""
        reply = await self._http.get("/config")
        reply.raise_for_status()
        return reply.json()

    async def reload_config(self) -> None:
        """Make every folder read the configuration file again, ending their running turns.

        opencode reads the file the first time a folder is used and keeps what
        it read, so a rewrite counts only after this.
        """
        reply = await self._http.post("/global/dispose")
        reply.raise_for_status()

    async def create_session(self, directory: Path, title: str) -> str:
        """Open a session; with a title, opencode never asks the model for one."""
        reply = await self._http.post(
            "/session", params=_in(directory), json={"title": title}
        )
        reply.raise_for_status()
        return reply.json()["id"]

    async def delete_session(self, directory: Path, session_id: str) -> None:
        """Remove a session and everything it holds."""
        reply = await self._http.delete(f"/session/{session_id}", params=_in(directory))
        reply.raise_for_status()

    async def session_ids(self, directory: Path) -> set[str]:
        """The sessions opencode holds for this folder."""
        reply = await self._http.get("/session", params=_in(directory))
        reply.raise_for_status()
        return {session["id"] for session in reply.json()}

    async def status(self, directory: Path, session_id: str) -> str:
        """`busy`, `retry` or `idle`; opencode lists only sessions that are not idle."""
        reply = await self._http.get("/session/status", params=_in(directory))
        reply.raise_for_status()
        return reply.json().get(session_id, {}).get("type", "idle")

    async def messages(self, directory: Path, session_id: str) -> list[dict[str, Any]]:
        """Every message of the session, oldest first, each with its parts."""
        reply = await self._http.get(
            f"/session/{session_id}/message", params=_in(directory)
        )
        reply.raise_for_status()
        return reply.json()

    async def send_turn(
        self, directory: Path, session_id: str, text: str, *, model: str
    ) -> None:
        """Start a turn and return at once; what happens next arrives as events.

        The model is named on every turn, so a session keeps working after the
        selected model, and with it opencode's configuration, changes.
        """
        body = {
            "agent": AGENT,
            "model": {"providerID": PROVIDER, "modelID": model},
            "parts": [{"type": "text", "text": text}],
        }
        reply = await self._http.post(
            f"/session/{session_id}/prompt_async", params=_in(directory), json=body
        )
        reply.raise_for_status()

    async def abort(self, directory: Path, session_id: str) -> None:
        """Stop the session's running turn."""
        reply = await self._http.post(
            f"/session/{session_id}/abort", params=_in(directory)
        )
        reply.raise_for_status()

    async def reply(
        self, directory: Path, request_id: str, reply: Literal["once", "reject"]
    ) -> None:
        """Answer a permission request; SurfSense never answers "always"."""
        answered = await self._http.post(
            f"/permission/{request_id}/reply",
            params=_in(directory),
            json={"reply": reply},
        )
        answered.raise_for_status()

    async def add_tool_server(
        self, directory: Path, name: str, url: str, headers: dict[str, str]
    ) -> str:
        """Point the folder's opencode at a remote MCP server; its status once it tried to connect.

        Kept by that folder's instance alone, and forgotten when opencode reloads.
        """
        added = await self._http.post(
            "/mcp",
            params=_in(directory),
            json={
                "name": name,
                "config": {
                    "type": "remote",
                    "url": url,
                    "headers": headers,
                    # Otherwise a refused key starts OAuth discovery against SurfSense.
                    "oauth": False,
                },
            },
        )
        added.raise_for_status()
        return added.json().get(name, {}).get("status", "unknown")

    def events(self, directory: Path) -> AsyncIterator[Event]:
        """The folder's event stream, until it drops or falls silent."""
        return read_events(self._http, directory)


def _in(directory: Path) -> dict[str, str]:
    """The query that routes a call to the folder's own opencode instance."""
    return {"directory": str(directory)}
