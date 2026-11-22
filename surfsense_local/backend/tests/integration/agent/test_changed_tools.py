"""The check of changed tools before and after a turn, against a real server on loopback."""

import asyncio
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from modules.agent.plugin_tools import changed_tools
from modules.agent.plugin_tools.changed_tools import (
    check_after_turn,
    check_changed_tools,
)
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.installed.third_party import set_third_party_on
from shared.db import create_session_factory
from tests.mcp_test_server import Delaying, notes_server, serving

pytestmark = pytest.mark.integration

SEARCH = SourceTool(
    name="search",
    title=None,
    description="Search the notes.",
    input_schema={},
    annotations={"readOnlyHint": True},
)


@pytest.fixture(autouse=True)
def plugins_checked_every_turn() -> None:
    """Here the intervals themselves are tested, so the conftest's every turn is not."""


@pytest.fixture
def slow_listing() -> Iterator[tuple[Delaying, str]]:
    """The notes server, each listing of its tools held 1 s."""
    app = Delaying(notes_server().streamable_http_app(), "tools/list", 1)
    with serving(app) as base:
        yield app, f"{base}/mcp"


def connected(engine: Engine, url: str, checked_ago: float) -> sessionmaker[Session]:
    """The notes plugin connected at `url`, last checked `checked_ago` seconds ago."""
    sessions = create_session_factory(engine)
    with sessions() as session:
        plugin = store_custom_plugin(session, "notes", "Notes", url, None, [SEARCH])
        plugin.checked_at = datetime.now(UTC) - timedelta(seconds=checked_ago)
        set_third_party_on(session, True)
        session.commit()
    return sessions


def checked_at(sessions: sessionmaker[Session]) -> datetime:
    """When the notes plugin was last checked."""
    with sessions() as session:
        return session.get_one(InstalledPlugin, "notes").checked_at.replace(tzinfo=UTC)


async def test_a_turn_waits_on_a_check_no_longer_than_its_deadline(
    engine: Engine, slow_listing: tuple[Delaying, str]
) -> None:
    """The turn keeps what was recorded; the listing is recorded once it ends."""
    app, url = slow_listing
    sessions = connected(engine, url, changed_tools.CHECK_SECONDS + 1)
    before = checked_at(sessions)
    began = time.monotonic()

    in_time = await check_changed_tools(sessions, deadline=0.2)

    assert time.monotonic() - began < 1
    assert in_time == 0
    assert checked_at(sessions) == before
    await changed_tools._checking["notes"]
    assert checked_at(sessions) > before
    assert len(app.held) == 1


async def test_a_check_already_running_is_waited_on_not_run_again(
    engine: Engine, slow_listing: tuple[Delaying, str]
) -> None:
    """Two turns starting together list the server once."""
    app, url = slow_listing
    sessions = connected(engine, url, changed_tools.CHECK_SECONDS + 1)

    counts = await asyncio.gather(
        check_changed_tools(sessions), check_changed_tools(sessions)
    )

    assert counts == [1, 1]
    assert len(app.held) == 1


async def test_a_plugin_checked_recently_is_not_listed(
    engine: Engine, slow_listing: tuple[Delaying, str]
) -> None:
    """Before a turn, at most once every CHECK_SECONDS."""
    app, url = slow_listing
    sessions = connected(engine, url, 10)

    assert await check_changed_tools(sessions) == 0
    assert app.held == []


async def test_after_a_turn_plugins_checked_a_while_ago_are_listed(
    engine: Engine, slow_listing: tuple[Delaying, str]
) -> None:
    """In the background, so the next turn finds its check done."""
    app, url = slow_listing
    sessions = connected(engine, url, changed_tools.AFTER_TURN_SECONDS + 1)
    before = checked_at(sessions)

    check_after_turn(sessions)
    (running,) = changed_tools._after_turn
    await running

    assert checked_at(sessions) > before
    assert len(app.held) == 1


async def test_after_a_turn_plugins_checked_just_now_are_left(
    engine: Engine, slow_listing: tuple[Delaying, str]
) -> None:
    """A check after every turn would list each server many times a minute."""
    app, url = slow_listing
    sessions = connected(engine, url, changed_tools.AFTER_TURN_SECONDS - 60)

    check_after_turn(sessions)
    (running,) = changed_tools._after_turn
    await running

    assert app.held == []
