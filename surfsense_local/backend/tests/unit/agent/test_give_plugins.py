"""Giving a turn's plugins to opencode: all at once, each failing alone, and the rules always set."""

import asyncio
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from modules.agent.plugin_tools import give_plugins as giving
from modules.agent.plugin_tools.give_plugins import give_plugins
from modules.agent.plugin_tools.given_servers import digest, given_as, remember_given
from modules.agent.plugin_tools.thread_calls import CALLS_HEADER
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin
from modules.agent.tool_endpoint.registration import (
    PLUGIN_CALL_SECONDS,
    TOOL_CALL_SECONDS,
)

pytestmark = pytest.mark.unit


class _Opencode:
    """Answers each add after its server's delay; `None` never answers, an error fails it."""

    def __init__(self, delays: dict[str, float | Exception | None]) -> None:
        self.delays = delays
        self.timeouts: dict[str, int] = {}
        self.dropped: list[str] = []
        self.rules: list[dict[str, str]] | None = None

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
        self.timeouts[name] = timeout_seconds
        delay = self.delays[name]
        if isinstance(delay, Exception):
            raise delay
        await asyncio.sleep(3600 if delay is None else delay)
        return "connected"

    async def drop_tool_server(self, directory: Path, name: str) -> None:
        self.dropped.append(name)

    async def set_session_rules(
        self, session_id: str, rules: list[dict[str, str]]
    ) -> None:
        self.rules = rules


def plugin(name: str, *, ours: bool = False) -> TurnPlugin:
    """A ready plugin with one tool; `ours` is on SurfSense's plugin host."""
    headers = {CALLS_HEADER: "t"} if ours else {}
    return TurnPlugin(
        name=name,
        title=name.title(),
        url=f"https://{name}.example/mcp",
        headers=headers,
        rules={f"{name}_search": "allow"},
        on_plugin_host=ours,
    )


async def test_plugins_are_given_at_once(tmp_path: Path) -> None:
    """The turn waits for the slowest server, not for the sum of them."""
    opencode = _Opencode({"a": 0.3, "b": 0.3, "c": 0.3})
    began = time.monotonic()

    given = await give_plugins(
        opencode, tmp_path, {}, [plugin("a"), plugin("b"), plugin("c")]
    )

    assert time.monotonic() - began < 0.8
    assert (given.unavailable, given.added) == ([], 3)


async def test_a_server_that_hangs_or_fails_is_named_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The others are given, and only an answered add is remembered as given."""
    monkeypatch.setattr(giving, "CONNECT_SECONDS", 0.2)
    opencode = _Opencode({"a": 0, "hung": None, "down": httpx.ConnectError("refused")})
    held: dict[str, str] = {}

    given = await give_plugins(
        opencode, tmp_path, held, [plugin("a"), plugin("hung"), plugin("down")]
    )

    assert given.unavailable == [
        UnavailablePlugin("Hung", "unreachable"),
        UnavailablePlugin("Down", "unreachable"),
    ]
    assert given.added == 1
    assert held == {"a": "connected"}
    assert given_as(tmp_path, "a") == digest(plugin("a"))
    assert given_as(tmp_path, "hung") is None


async def test_a_server_held_as_given_is_left_and_one_no_longer_ready_dropped(
    tmp_path: Path,
) -> None:
    """Giving it again would open a new MCP session; SurfSense's own server is never dropped."""
    remember_given(tmp_path, "a", digest(plugin("a")))
    opencode = _Opencode({})
    held = {"a": "connected", "gone": "connected", "surfsense": "connected"}

    given = await give_plugins(opencode, tmp_path, held, [plugin("a")])

    assert (given.unavailable, given.added) == ([], 0)
    assert opencode.dropped == ["gone"]


async def test_surfsense_s_plugins_get_the_longer_call_timeout(tmp_path: Path) -> None:
    """A scrape runs minutes; any other server keeps the tools' own limit."""
    opencode = _Opencode({"ours": 0, "theirs": 0})

    await give_plugins(
        opencode, tmp_path, {}, [plugin("ours", ours=True), plugin("theirs")]
    )

    assert opencode.timeouts == {
        "ours": PLUGIN_CALL_SECONDS,
        "theirs": TOOL_CALL_SECONDS,
    }


async def test_a_server_that_failed_this_turn_is_not_waited_on_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second giving, after the check changed the list, names it at once; one given anew is tried."""
    monkeypatch.setattr(giving, "CONNECT_SECONDS", 0.2)
    opencode = _Opencode({"hung": None, "b": 0})
    held: dict[str, str] = {}
    first = await give_plugins(opencode, tmp_path, held, [plugin("hung")])
    opencode.delays["hung"] = 0
    began = time.monotonic()

    again = await give_plugins(
        opencode, tmp_path, held, [plugin("hung"), plugin("b")], first.failed
    )

    assert time.monotonic() - began < 0.15
    assert first.failed == {("hung", digest(plugin("hung")))}
    assert again.unavailable == [UnavailablePlugin("Hung", "unreachable")]
    assert (again.added, again.failed) == (1, first.failed)
    # Its headers changed at the check, a refreshed sign-in say: given anew.
    signed_in = replace(plugin("hung"), headers={"k": "new"})
    renewed = await give_plugins(opencode, tmp_path, held, [signed_in], first.failed)
    assert (renewed.unavailable, renewed.added) == ([], 1)


class _AsksForSignIn(_Opencode):
    """Answers every server added as needing sign-in."""

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
        return "needs_auth"


async def test_a_refused_license_is_named_as_one_not_as_a_sign_in(
    tmp_path: Path,
) -> None:
    """A paid plugin's refusal is its license; signing in again would not help."""
    plugins = [
        replace(plugin("amazon", ours=True), licensed=True),
        plugin("notion"),
    ]

    given = await give_plugins(_AsksForSignIn({}), tmp_path, {}, plugins)

    assert given.unavailable == [
        UnavailablePlugin("Amazon", "license"),
        UnavailablePlugin("Notion", "sign_in"),
    ]
