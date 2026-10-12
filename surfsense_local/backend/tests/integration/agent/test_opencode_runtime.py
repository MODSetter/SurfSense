"""Getting an opencode that runs SurfSense's current configuration, before a turn uses it."""

import asyncio
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

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
    (agent_dir / "opencode-failed.json").write_text(
        '{"reason": "opencode exited with code 7"}', encoding="utf-8"
    )

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
            # opencode reads its configuration when a folder is first used, and keeps it.
            assert (await earlier.config())["provider"]["surfsense"]["options"][
                "apiKey"
            ] == "old-key"

        ready = await ready_opencode(session, launch_key="new-key")
        try:
            loaded = await ready.client.config()
        finally:
            await ready.client.close()

    assert loaded["provider"]["surfsense"]["options"]["apiKey"] == "new-key"
    assert ready.model == "remote-model"
    # Applied by opencode's own reload: no restart, so no turn elsewhere is cut off by one later.
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
            await earlier.config()  # opencode reads the folder's configuration now

        ready = await ready_opencode(session, launch_key="same-key")
        try:
            loaded = await ready.client.config()
        finally:
            await ready.client.close()

    model = loaded["provider"]["surfsense"]["models"]["gpt-4o-mini"]
    assert model["modalities"]["input"] == ["text", "image"]
    assert model["attachment"] is True
