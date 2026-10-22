"""Getting an opencode that runs SurfSense's current configuration, before a turn uses it."""

import asyncio
import os
import secrets
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent import opencode_config, opencode_runtime
from modules.agent.model_window import selected_model_window
from modules.agent.opencode_client import OpencodeClient
from modules.agent.opencode_config import AgentSetup, write_opencode_config
from modules.agent.opencode_runtime import AgentUnavailableError, ready_opencode
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_session_factory
from tests.integration.agent.opencode_harness import (
    StandInForElectron,
    free_port,
    needs_staged_opencode,
    wait_until_healthy,
)

pytestmark = pytest.mark.integration


class ElectronGivingUpAfterEachStart:
    """Electron's side of a crashing opencode: each newer configuration earns one start, which fails."""

    def __init__(self, agent_dir: Path) -> None:
        self.config = agent_dir / "opencode.json"
        self.failure = agent_dir / "opencode-failed.json"
        self.config.unlink(missing_ok=True)
        self.failure.unlink(missing_ok=True)
        self.starts = 0

    async def run(self) -> None:
        """Give up after every start, as three quick exits do."""
        gave_up_at = 0.0
        while True:
            if self.config.exists() and self.config.stat().st_mtime > gave_up_at:
                self.starts += 1
                await asyncio.sleep(0.3)  # three quick exits take a while
                self.failure.write_text(
                    '{"reason": "opencode exited with code 7"}', encoding="utf-8"
                )
                gave_up_at = self.failure.stat().st_mtime
            await asyncio.sleep(0.05)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on this test's migrated database, with a remote model selected."""
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label="Remote",
            provider="openai_compatible",
            base_url="http://127.0.0.1:1/v1",
        )
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name="remote-model",
            )
        )
        session.commit()
        yield session


async def test_without_a_staged_opencode_the_agent_is_unavailable(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron passes no address where no opencode was staged."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)

    with pytest.raises(AgentUnavailableError):
        await ready_opencode(session, launch_key="new-key")


async def test_an_opencode_electron_gave_up_on_fails_the_turn_at_once(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron says so after this turn's configuration, so nothing waits the full minute."""
    agent_dir: Path = get_storage_settings().agent_dir
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{free_port()}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", "password")
    config = agent_dir / "opencode.json"
    config.unlink(missing_ok=True)

    async def electron_gives_up() -> None:
        while not config.exists():
            await asyncio.sleep(0.05)
        (agent_dir / "opencode-failed.json").write_text(
            '{"reason": "opencode exited with code 7"}', encoding="utf-8"
        )

    giving_up = asyncio.create_task(electron_gives_up())
    with pytest.raises(AgentUnavailableError, match="opencode exited with code 7"):
        await asyncio.wait_for(ready_opencode(session, launch_key="key"), 5)
    await giving_up


async def test_asking_again_after_electron_gave_up_earns_another_start(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same setup writes the same file, and Electron starts a given-up opencode only for a newer one."""
    agent_dir: Path = get_storage_settings().agent_dir
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{free_port()}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", "password")
    electron = ElectronGivingUpAfterEachStart(agent_dir)
    giving_up = asyncio.create_task(electron.run())
    try:
        for expected in (1, 2, 3):
            with pytest.raises(AgentUnavailableError, match="code 7"):
                await asyncio.wait_for(ready_opencode(session, launch_key="key"), 5)
            assert electron.starts == expected
    finally:
        giving_up.cancel()


async def test_reading_a_thread_back_after_electron_gave_up_earns_no_start(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The history read that follows a failed turn must not start opencode a second time."""
    agent_dir: Path = get_storage_settings().agent_dir
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{free_port()}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", "password")
    electron = ElectronGivingUpAfterEachStart(agent_dir)
    giving_up = asyncio.create_task(electron.run())
    try:
        with pytest.raises(AgentUnavailableError, match="code 7"):
            await asyncio.wait_for(ready_opencode(session, launch_key="key"), 5)
        written = electron.config.stat().st_mtime

        with pytest.raises(AgentUnavailableError, match="code 7"):
            await asyncio.wait_for(
                ready_opencode(session, launch_key="key", earns_a_start=False), 5
            )
        await asyncio.sleep(0.2)

        assert electron.config.stat().st_mtime == written
        assert electron.starts == 1
    finally:
        giving_up.cancel()


async def test_a_failure_from_before_this_turn_s_configuration_is_not_read(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asking again earns opencode another start, so an earlier failure says nothing yet."""
    agent_dir: Path = get_storage_settings().agent_dir
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{free_port()}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", "password")
    monkeypatch.setattr("modules.agent.opencode_runtime.READY_SECONDS", 0.5)
    agent_dir.mkdir(parents=True, exist_ok=True)
    failure = agent_dir / "opencode-failed.json"
    failure.write_text('{"reason": "opencode exited with code 7"}', encoding="utf-8")
    # Windows file times move in ~16 ms ticks, so a fresh failure can tie the config.
    earlier = time.time() - 60
    os.utime(failure, (earlier, earlier))

    with pytest.raises(AgentUnavailableError, match="did not start"):
        await ready_opencode(session, launch_key="key")


async def test_it_waits_for_the_configuration_it_just_wrote(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opencode already running read the previous configuration, with a key no longer valid."""
    needs_staged_opencode()
    agent_dir: Path = get_storage_settings().agent_dir
    port, password = free_port(), secrets.token_urlsafe(16)
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{port}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", password)
    old = AgentSetup(
        model="remote-model",
        window=32768,
        reads_images=False,
        endpoint_url="http://127.0.0.1:1/v1",
        launch_key="old-key",
        route="chat_completions",
    )
    write_opencode_config(agent_dir / "opencode.json", old)

    with StandInForElectron(agent_dir, port, password) as electron:
        assert electron.running is not None
        await asyncio.to_thread(wait_until_healthy, electron.running)
        async with OpencodeClient(electron.running.url, password) as earlier:
            loaded = await earlier.config(agent_dir)
            assert loaded["providers"]["surfsense"]["settings"]["apiKey"] == "old-key"

        ready = await ready_opencode(session, launch_key="new-key")
        try:
            loaded = await ready.client.config(agent_dir)
        finally:
            await ready.client.close()

    assert loaded["providers"]["surfsense"]["settings"]["apiKey"] == "new-key"
    assert ready.model == "remote-model"
    # Loaded by opencode watching the file: no restart, so no turn elsewhere is cut off by one.
    assert electron.starts == 1


async def test_a_model_that_comes_to_read_images_is_reloaded_with_image_input(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same model, window and key, but now it reads images: the configuration served is not this one."""
    needs_staged_opencode()
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    assert selected is not None
    selected.name = "gpt-4o-mini"
    session.get(ProviderConnection, selected.connection_id).catalog_provider = "openai"
    session.commit()
    _, window = await selected_model_window(session)
    agent_dir: Path = get_storage_settings().agent_dir
    port, password = free_port(), secrets.token_urlsafe(16)
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{port}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", password)
    without_images = AgentSetup(
        model="gpt-4o-mini",
        window=window,
        reads_images=False,
        endpoint_url="http://127.0.0.1:1/v1",
        launch_key="same-key",
        route="chat_completions",
    )
    write_opencode_config(agent_dir / "opencode.json", without_images)

    with StandInForElectron(agent_dir, port, password) as electron:
        assert electron.running is not None
        await asyncio.to_thread(wait_until_healthy, electron.running)
        async with OpencodeClient(electron.running.url, password) as earlier:
            loaded = await earlier.config(agent_dir)
            model = loaded["providers"]["surfsense"]["models"]["gpt-4o-mini"]
            assert model["capabilities"]["input"] == ["text"]

        ready = await ready_opencode(session, launch_key="same-key")
        try:
            loaded = await ready.client.config(agent_dir)
        finally:
            await ready.client.close()

    model = loaded["providers"]["surfsense"]["models"]["gpt-4o-mini"]
    assert model["capabilities"]["input"] == ["text", "image"]


async def test_a_value_opencode_refuses_stops_the_turn_rather_than_the_agent_vanishing(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One value opencode refuses drops the object holding it, here the agent, with
    only a line in its log; every prompt would then fail with "Agent not found"."""
    needs_staged_opencode()
    agent_dir: Path = get_storage_settings().agent_dir
    port, password = free_port(), secrets.token_urlsafe(16)
    monkeypatch.setattr(
        get_agent_settings(), "opencode_url", f"http://127.0.0.1:{port}"
    )
    monkeypatch.setattr(get_agent_settings(), "opencode_password", password)
    monkeypatch.setattr(opencode_runtime, "READY_SECONDS", 5.0)
    written = opencode_config.opencode_config

    def with_a_refused_value(setup: AgentSetup, at: Path) -> dict:
        config = written(setup, at)
        config["agents"]["surfsense"]["steps"] = -1  # steps must be positive
        return config

    monkeypatch.setattr(opencode_config, "opencode_config", with_a_refused_value)

    task = asyncio.create_task(ready_opencode(session, launch_key="key"))
    with (
        StandInForElectron(agent_dir, port, password),
        pytest.raises(AgentUnavailableError, match="as written"),
    ):
        await task
