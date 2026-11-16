import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, Literal, Self

import httpx

from modules.agent.opencode_client.events import read_events
from modules.agent.opencode_client.payloads import Event
from modules.agent.opencode_config import AGENT, PROVIDER

# The release runtimes/opencode/pins.mjs stages; its HTTP API is unversioned.
OPENCODE_VERSION = "2.1.2"

# Every call but the event stream answers at once; a server that does not was
# seen to accept a connection and never reply while starting.
_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
_HEALTH_TIMEOUT = httpx.Timeout(3.0, connect=2.0)
# The most opencode returns in one page of a listing.
_PAGE = 200
# opencode rebuilds what a step is offered 100 ms after a server connects
# (core/src/tool/mcp.ts); a prompt sent before then starts without its tools.
_TOOLS_SETTLE_SECONDS = 0.4


class OpencodeVersionError(RuntimeError):
    """The opencode that answered is not the release SurfSense was written against."""


class OpencodeClient:
    """The backend's calls to opencode. A call about a session runs where the
    session was made; the rest name the folder they are about."""

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
        """The release the running server reports; it answers 503 until it is ready."""
        return (await self._info())["version"]

    async def server_pid(self) -> int:
        """The running server's process, which tells one start from the next."""
        return (await self._info())["pid"]

    async def require_pinned_version(self) -> None:
        """Refuse to go on with any opencode but the pinned one."""
        running = await self.version()
        if running != OPENCODE_VERSION:
            raise OpencodeVersionError(
                f"opencode {running} is running; SurfSense speaks {OPENCODE_VERSION}"
            )

    async def config(self, directory: Path) -> dict[str, Any]:
        """The configuration file as opencode loaded it, in its own shape.

        The file is watched: a rewrite is loaded in about 0.3 s, with no call.
        """
        reply = await self._http.get("/api/config", params=_located(directory))
        reply.raise_for_status()
        for source in reply.json():
            if source.get("type") == "document":
                return source.get("info") or {}
        return {}

    async def create_session(self, directory: Path, title: str, *, model: str) -> str:
        """Open a session; with a title, opencode never asks the model for one."""
        reply = await self._http.post(
            "/api/session",
            json={
                "title": title,
                "agent": AGENT,
                "model": {"providerID": PROVIDER, "id": model},
                "location": {"directory": str(directory)},
            },
        )
        reply.raise_for_status()
        return reply.json()["data"]["id"]

    async def delete_session(self, session_id: str) -> None:
        """Remove a session and everything it holds."""
        reply = await self._http.delete(f"/api/session/{session_id}")
        reply.raise_for_status()

    async def session_directory(self, session_id: str) -> str:
        """The folder a session was created in, where every call about it runs."""
        return (await self._session(session_id))["location"]["directory"]

    async def session_metadata(self, session_id: str) -> dict[str, Any]:
        """What callers stored on the session; opencode itself writes none."""
        return (await self._session(session_id)).get("metadata") or {}

    async def set_session_metadata(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        """Replace the session's metadata whole: opencode does not merge it."""
        reply = await self._http.patch(
            f"/api/session/{session_id}", json={"metadata": metadata}
        )
        reply.raise_for_status()

    async def dispose_instance(self, directory: Path) -> None:
        """Drop the folder's instance: its MCP servers, its config and its memory.

        opencode keeps one per folder until it exits; the next call there starts a new one.
        """
        reply = await self._http.delete(
            "/api/debug/location", params=_located(directory)
        )
        reply.raise_for_status()

    async def session_ids(self, directory: Path) -> set[str]:
        """The sessions opencode holds for this folder."""
        return {
            session["id"]
            async for session in self._pages(
                "/api/session", {"directory": str(directory)}
            )
        }

    async def status(self, session_id: str) -> Literal["running", "idle"]:
        """Whether the session is running a turn; opencode lists only those that are."""
        reply = await self._http.get("/api/session/active")
        reply.raise_for_status()
        return "running" if session_id in reply.json()["data"] else "idle"

    async def messages(self, session_id: str) -> list[dict[str, Any]]:
        """Every message of the session, oldest first, each one tagged by `type`."""
        return [
            message
            async for message in self._pages(
                f"/api/session/{session_id}/message", {"order": "asc"}
            )
        ]

    async def send_turn(
        self,
        session_id: str,
        text: str,
        *,
        model: str,
        notes: Sequence[str] = (),
    ) -> str:
        """Start a turn and return its user message's id at once; what happens
        next arrives as events.

        The model is set when it changed, so a session keeps working after the
        selected model, and with it opencode's configuration, changes. Each of
        `notes` goes before the user's words as a synthetic message: the model
        reads it, and it is kept apart from the user's.
        """
        held = await self._session(session_id)
        wanted = {"providerID": PROVIDER, "id": model}
        if {k: (held.get("model") or {}).get(k) for k in wanted} != wanted:
            await self._post(f"/api/session/{session_id}/model", {"model": wanted})
        if held.get("agent") != AGENT:
            await self._post(f"/api/session/{session_id}/agent", {"agent": AGENT})
        for note in notes:
            # Held until the prompt, so the turn starts once, with both.
            await self._post(
                f"/api/session/{session_id}/synthetic", {"text": note, "resume": False}
            )
        sent = await self._post(f"/api/session/{session_id}/prompt", {"text": text})
        return sent["data"]["id"]

    async def abort(self, session_id: str) -> None:
        """Stop the session's running turn."""
        reply = await self._http.post(f"/api/session/{session_id}/interrupt")
        reply.raise_for_status()

    async def reply(
        self, session_id: str, request_id: str, reply: Literal["once", "reject"]
    ) -> None:
        """Answer a permission request; SurfSense never answers "always"."""
        answered = await self._http.post(
            f"/api/session/{session_id}/permission/{request_id}/reply",
            json={"decision": reply},
        )
        answered.raise_for_status()

    async def add_tool_server(
        self,
        directory: Path,
        name: str,
        url: str,
        headers: dict[str, str],
        *,
        timeout_seconds: int,
        connect_seconds: int,
    ) -> str:
        """Point the folder's opencode at a remote MCP server; its status once it tried to connect.

        Kept by that folder's instance alone, and forgotten when the instance goes.
        A call to one of its tools fails after `timeout_seconds`, and connecting
        after `connect_seconds`.

        Added on, a server is connected under one lock with every other being
        added to the folder, and listing waits on each (core/src/mcp/index.ts),
        so one that hangs would hold the rest. Added off, then connected, each
        connects on its own, and the connect answers once it has.
        """
        location = _located(directory)
        added = await self._http.put(
            f"/api/experimental/mcp/{name}",
            params=location,
            json={
                "config": {
                    "disabled": True,
                    "type": "remote",
                    "url": url,
                    "headers": headers,
                    # Otherwise a refused key starts OAuth discovery against SurfSense.
                    "oauth": False,
                    # Code Mode would store no output and link no approval to its calls.
                    "codemode": False,
                    "timeout": {
                        "startup": connect_seconds * 1000,
                        "execution": timeout_seconds * 1000,
                    },
                }
            },
        )
        added.raise_for_status()
        connected = await self._http.post(
            f"/api/experimental/mcp/{name}/connect",
            params=location,
            timeout=httpx.Timeout(connect_seconds + 10.0, connect=5.0),
        )
        connected.raise_for_status()
        status = (await self.tool_servers(directory)).get(name, "unknown")
        if status == "connected":
            await asyncio.sleep(_TOOLS_SETTLE_SECONDS)
        return status

    async def tool_servers(self, directory: Path) -> dict[str, str]:
        """Each MCP server the folder's instance holds, by name, with its status."""
        reply = await self._http.get("/api/mcp", params=_located(directory))
        reply.raise_for_status()
        return {
            held["name"]: (held.get("status") or {}).get("status", "unknown")
            for held in reply.json()["data"]
        }

    async def drop_tool_server(self, directory: Path, name: str) -> None:
        """Remove the server from the folder's instance; its tools leave the next step."""
        reply = await self._http.delete(
            f"/api/experimental/mcp/{name}", params=_located(directory)
        )
        reply.raise_for_status()

    async def set_session_rules(
        self, session_id: str, rules: list[dict[str, str]]
    ) -> None:
        """Replace the session's rules, which come after the configuration's; the
        last that matches wins. opencode reads them before every step.

        A denied tool is also left out of what the model is offered.
        """
        reply = await self._http.patch(
            f"/api/session/{session_id}",
            json={
                "permissions": [
                    {
                        "action": rule["permission"],
                        "resource": rule["pattern"],
                        "effect": rule["action"],
                    }
                    for rule in rules
                ]
            },
        )
        reply.raise_for_status()

    def events(self) -> AsyncIterator[Event]:
        """Every folder's events, until the stream drops or falls silent."""
        return read_events(self._http)

    async def _info(self) -> dict[str, Any]:
        reply = await self._http.get("/api/info", timeout=_HEALTH_TIMEOUT)
        reply.raise_for_status()
        return reply.json()

    async def _session(self, session_id: str) -> dict[str, Any]:
        reply = await self._http.get(f"/api/session/{session_id}")
        reply.raise_for_status()
        return reply.json()["data"]

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        reply = await self._http.post(path, json=body)
        reply.raise_for_status()
        return reply.json() if reply.content else {}

    async def _pages(
        self, path: str, params: dict[str, str]
    ) -> AsyncIterator[dict[str, Any]]:
        """Each item of a listing opencode pages, following its cursor."""
        cursor: str | None = None
        while True:
            # A cursor carries the listing's filters; opencode refuses them beside it.
            page = {"cursor": cursor} if cursor is not None else dict(params)
            reply = await self._http.get(path, params={**page, "limit": str(_PAGE)})
            reply.raise_for_status()
            body = reply.json()
            for item in body["data"]:
                yield item
            cursor = (body.get("cursor") or {}).get("next")
            if not body["data"] or cursor is None:
                return


def _located(directory: Path) -> dict[str, str]:
    """The query that routes a call to the folder's own opencode instance."""
    return {"location[directory]": str(directory)}
