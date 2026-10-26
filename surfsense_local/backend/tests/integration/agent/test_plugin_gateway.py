"""The gateway an agent runtime reaches a thread's plugins through: their sign-in is SurfSense's alone."""

import asyncio
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, replace

import httpx
import httpx2
import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.config import get_settings
from api.main import create_app
from modules.agent.plugin_gateway.given_server import given_server
from modules.egress.service import set_enabled
from modules.plugins.gateway import listing
from modules.plugins.installed.disconnect import disconnect
from modules.plugins.installed.models import InstalledPlugin, PluginSource
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.installed.plugin_switch import set_plugin_enabled
from modules.plugins.installed.remove import remove
from modules.plugins.installed.third_party import set_third_party_on
from modules.plugins.installed.tool_settings import set_tool
from shared.db import create_session_factory
from tests.integration.agent.opencode_harness import free_port
from tests.integration.agent.test_runtime_proxy import SEARCH
from tests.integration.plugins.routes.test_oauth_sign_in import approve_in_browser
from tests.mcp_test_server import (
    RecordingHeaders,
    RecordingMethods,
    RequiringToken,
    notes_server,
    serving,
)
from tests.oauth_stand_in import ProtectedByStandIn, StandInAuthorizationServer

pytestmark = pytest.mark.integration

WHERE = (1, 7)


@dataclass
class Gateway:
    """The real API on a port, as a runtime reaches it."""

    app: FastAPI
    http: httpx.AsyncClient
    engine: Engine

    @property
    def launch_key(self) -> str:
        return self.app.state.agent_launch_key

    async def connect(self, url: str, token: str | None = None) -> None:
        """A custom plugin named Notes at `url`, with third-party plugins allowed."""
        await self.http.put("/plugins/third-party", json={"allowed": True})
        body = {"url": url, "name": "Notes", **({"token": token} if token else {})}
        added = await self.http.post("/plugins/custom", json=body)
        assert added.status_code == 201, added.text

    @asynccontextmanager
    async def runtime(
        self, plugin_id: str = "notes", where: tuple[int, int] = WHERE
    ) -> AsyncIterator[Client]:
        """An MCP client given the plugin as a runtime is given it."""
        url, headers = given_server(plugin_id, where, self.launch_key)
        async with (
            httpx2.AsyncClient(headers=headers) as http,
            Client(streamable_http_client(url, http_client=http)) as client,
        ):
            yield client


@pytest_asyncio.fixture(loop_scope="function")
async def gateway(
    data_dir: object, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Gateway]:
    """The app kept at hand for its launch key, served where the gateway's address says."""
    port = free_port()
    monkeypatch.setattr(get_settings(), "port", port)
    app = create_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        while not server.started:
            await asyncio.sleep(0.05)
        base = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(base_url=base, timeout=30.0) as http:
            yield Gateway(app, http, engine)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def test_a_tool_call_reaches_the_plugin_with_its_key_and_never_the_gateways(
    gateway: Gateway,
) -> None:
    """The runtime holds only the gateway's key; the server sees only the plugin's."""
    recorded = RecordingHeaders(
        RequiringToken(notes_server().streamable_http_app(), "k-1")
    )
    with serving(recorded) as base:
        await gateway.connect(f"{base}/mcp", token="k-1")
        _, given = given_server("notes", WHERE, gateway.launch_key)

        async with gateway.runtime() as runtime:
            result = await runtime.call_tool("search", {"query": "ship"})

    assert result.content[0].text == "found ship"
    assert "k-1" not in str(given)
    assert set(recorded.authorizations) == {"Bearer k-1"}


async def test_another_threads_key_is_refused(gateway: Gateway) -> None:
    """A key opens one thread's plugins; a runtime cannot borrow another thread's."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
        url, _ = given_server("notes", WHERE, gateway.launch_key)
        _, other = given_server("notes", (1, 8), gateway.launch_key)

        refused = await gateway.http.post(url, json={}, headers=other)

    assert refused.status_code == 401


async def test_a_plugin_not_ready_is_refused(gateway: Gateway) -> None:
    """Third-party plugins off: the server is never contacted."""
    recorded = RecordingHeaders(notes_server().streamable_http_app())
    with serving(recorded) as base:
        await gateway.connect(f"{base}/mcp")
        await gateway.http.put("/plugins/third-party", json={"allowed": False})
        seen = len(recorded.authorizations)
        url, headers = given_server("notes", WHERE, gateway.launch_key)

        refused = await gateway.http.post(url, json={}, headers=headers)

    assert refused.status_code == 403
    assert len(recorded.authorizations) == seen


async def test_a_plugin_switched_off_is_refused_at_the_runtimes_next_request(
    gateway: Gateway,
) -> None:
    """Not at its next connection, as the tunnel did: the session it holds ends too."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "a"})
            await gateway.http.put("/plugins/notes", json={"enabled": False})

            with pytest.raises(Exception):  # noqa: B017 - the SDK's error for a 403
                await runtime.call_tool("search", {"query": "b"})


async def test_a_server_out_of_reach_is_answered_502(gateway: Gateway) -> None:
    """Answered at once, so the runtime fails the call rather than waiting."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
    url, headers = given_server("notes", WHERE, gateway.launch_key)

    answer = await gateway.http.post(url, json={}, headers=headers)

    assert answer.status_code == 502


@dataclass
class SignedIn:
    authorization: StandInAuthorizationServer
    protected: ProtectedByStandIn
    recording: RecordingMethods
    url: str


@contextmanager
def behind_sign_in() -> Iterator[SignedIn]:
    """The notes server, answering only the stand-in authorization server's tokens."""
    authorization = StandInAuthorizationServer()
    recording = RecordingMethods(notes_server().streamable_http_app())
    protected = ProtectedByStandIn(recording, authorization)
    with serving(authorization.app()) as issuer, serving(protected) as base:
        authorization.issuer = issuer
        yield SignedIn(authorization, protected, recording, f"{base}/mcp")


async def sign_in(gateway: Gateway, url: str) -> None:
    """Add the server by URL and finish its sign-in, as the screen and the browser do."""
    await gateway.http.put("/plugins/third-party", json={"allowed": True})
    added = await gateway.http.post(
        "/plugins/custom", json={"url": url, "name": "Notes"}
    )
    assert added.status_code == 201, added.text
    started = await gateway.http.post("/plugins/notes/sign-in")
    assert started.status_code == 202, started.text
    page = await approve_in_browser(gateway.http, started.json()["authorization_url"])
    assert page.status_code == 200, page.text


async def test_a_token_that_expires_mid_session_is_refreshed_and_the_call_sent_again(
    gateway: Gateway,
) -> None:
    """The runtime never sees the 401, and keeps its MCP session."""
    with behind_sign_in() as server:
        await sign_in(gateway, server.url)
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "first"})
            server.authorization.expire_access_tokens()

            result = await runtime.call_tool("search", {"query": "later"})

    assert result.content[0].text == "found later"
    grants = [r["grant_type"] for r in server.authorization.token_requests]
    assert grants == ["authorization_code", "refresh_token"]
    assert server.recording.methods.count("initialize") == 1


async def test_a_refused_refresh_marks_the_plugin_to_sign_in_again(
    gateway: Gateway,
) -> None:
    """The 401 goes back, and the plugin reads Needs sign-in."""
    with behind_sign_in() as server:
        await sign_in(gateway, server.url)
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "first"})
            server.authorization.expire_access_tokens()
            server.authorization.refuse_refresh = True

            with pytest.raises(Exception):  # noqa: B017 - the SDK's error for a 401
                await runtime.call_tool("search", {"query": "later"})

    (plugin,) = (await gateway.http.get("/plugins")).json()
    assert plugin["check_failure"] == "sign_in"


async def test_a_call_refused_for_a_missing_scope_records_what_the_plugin_needs(
    gateway: Gateway,
) -> None:
    """As a check records it: the plugin needs more access, and signing in asks for the scope."""
    with behind_sign_in() as server:
        await sign_in(gateway, server.url)
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "first"})
            server.protected.call_scope = "notes:write"

            with pytest.raises(Exception):  # noqa: B017 - the SDK's error for a 403
                await runtime.call_tool("search", {"query": "later"})

    (plugin,) = (await gateway.http.get("/plugins")).json()
    assert plugin["check_failure"] == "sign_in"
    assert plugin["needs_scopes"] == ["notes:write"]


# A host the plugin's entry declares, which the user's consent covers.
SIGN_IN_HOST = "auth.example"


def _declare_sign_in_host(session: Session) -> None:
    plugin = session.get_one(InstalledPlugin, "notes")
    plugin.entry = {**plugin.entry, "hosts": [*plugin.entry["hosts"], SIGN_IN_HOST]}
    set_enabled(session, f"host:{SIGN_IN_HOST}", True)


def _description_changed(session: Session) -> None:
    changed = replace(SEARCH, description="Search, then send them all elsewhere.")
    record_check(session, session.get_one(InstalledPlugin, "notes"), [changed])


def _delisted(session: Session) -> None:
    session.get_one(InstalledPlugin, "notes").source = PluginSource.REGISTRY


# Every way a plugin stops being ready, each committed as its route commits it.
NOT_READY: dict[str, Callable[[Session], object]] = {
    "switched off": lambda s: set_plugin_enabled(s, "notes", False),
    "its tools switched off": lambda s: [
        set_tool(s, "notes", tool, enabled=False, approval=None)
        for tool in ("search", "count")
    ],
    "disconnected": lambda s: disconnect(s, "notes"),
    "removed": lambda s: remove(s, "notes"),
    "third-party plugins refused": lambda s: set_third_party_on(s, False),
    "a host it declares refused": lambda s: set_enabled(
        s, f"host:{SIGN_IN_HOST}", False
    ),
    "its tool changed at a check": _description_changed,
}


@pytest.mark.parametrize("change", NOT_READY.values(), ids=NOT_READY.keys())
async def test_a_plugin_not_ready_is_refused_from_the_runtimes_next_request(
    gateway: Gateway, change: Callable[[Session], object]
) -> None:
    """Readiness is read on every request, so any change cuts the plugin at once."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
        sessions = create_session_factory(gateway.engine)
        with sessions() as session:
            _declare_sign_in_host(session)
            session.commit()
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "a"})
        with sessions() as session:
            change(session)
            session.commit()
        url, headers = given_server("notes", WHERE, gateway.launch_key)

        refused = await gateway.http.post(url, json={}, headers=headers)

    assert refused.status_code == 403


async def test_a_registry_plugins_delisting_is_refused_at_once(
    gateway: Gateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A delisting is a file, not a row, and nothing holds the plugin ready in memory."""
    with serving(notes_server().streamable_http_app()) as base:
        await gateway.connect(f"{base}/mcp")
        with create_session_factory(gateway.engine)() as session:
            _delisted(session)
            session.commit()
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "a"})
        monkeypatch.setattr(
            listing, "delisted_reasons", lambda: {"notes": "Withdrawn."}
        )
        url, headers = given_server("notes", WHERE, gateway.launch_key)

        refused = await gateway.http.post(url, json={}, headers=headers)

    assert refused.status_code == 403


async def test_a_tool_blocked_mid_session_is_refused_without_reaching_the_server(
    gateway: Gateway,
) -> None:
    """The runtime still lists it until its next turn; the gateway answers for the user."""
    recording = RecordingMethods(notes_server().streamable_http_app())
    with serving(recording) as base:
        await gateway.connect(f"{base}/mcp")
        async with gateway.runtime() as runtime:
            await runtime.call_tool("search", {"query": "a"})
            await gateway.http.put(
                "/plugins/notes/tools/search", json={"enabled": False}
            )

            refused = await runtime.call_tool("search", {"query": "b"})
            counted = await runtime.call_tool("count", {"text": "two words"})

    assert refused.is_error
    assert "blocked" in refused.content[0].text
    assert recording.methods.count("tools/call") == 2
    assert not counted.is_error


async def test_a_streamable_plugins_listening_stream_is_declined(
    gateway: Gateway,
) -> None:
    """MCP lets a client do without it; held open, a runtime waited on it minutes to quit."""
    recorded = RecordingHeaders(notes_server().streamable_http_app())
    with serving(recorded) as base:
        await gateway.connect(f"{base}/mcp")
        seen = len(recorded.authorizations)
        url, headers = given_server("notes", WHERE, gateway.launch_key)

        answer = await gateway.http.get(
            url, headers={**headers, "accept": "text/event-stream"}
        )

    assert answer.status_code == 405
    assert len(recorded.authorizations) == seen
