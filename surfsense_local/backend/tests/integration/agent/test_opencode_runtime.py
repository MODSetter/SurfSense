"""Getting an opencode that runs SurfSense's current configuration, before a turn uses it."""

import asyncio
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

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
        endpoint_url="http://127.0.0.1:1/v1",
        launch_key="old-key",
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
