"""Nothing leaves the machine until the user allows that destination."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.models import ProviderConnection
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

REMOTE = {
    "label": "Cloud",
    "provider": "openai_compatible",
    "base_url": "https://api.provider.example/v1",
}


async def _destinations(client: AsyncClient) -> dict[str, dict]:
    reply = await client.get("/egress")
    assert reply.status_code == 200
    return {row["destination"]: row for row in reply.json()}


async def test_pull_is_refused_until_allowed_then_recorded(
    client: AsyncClient, ollama_server: str
) -> None:
    """Refused is a 403 the UI can act on; allowed runs and stamps the last call."""
    refused = await client.post(
        "/llm/providers/ollama/pull", json={"name": "qwen3:1.7b"}
    )
    assert refused.status_code == 403
    assert refused.json()["detail"] == {
        "code": "egress_disabled",
        "message": "sending data to registry.ollama.ai is off in Settings > Network",
        "destination": "ollama_pull",
        "host": "registry.ollama.ai",
    }
    assert (await _destinations(client))["ollama_pull"]["last_call_at"] is None

    assert (
        await client.put("/egress/ollama_pull", json={"enabled": True})
    ).status_code == 200
    async with client.stream(
        "POST", "/llm/providers/ollama/pull", json={"name": "qwen3:1.7b"}
    ) as reply:
        assert reply.status_code == 200
        await reply.aread()

    row = (await _destinations(client))["ollama_pull"]
    assert row["enabled"] is True
    assert row["last_call_at"] is not None


async def test_remote_connection_is_refused_before_it_is_probed(
    client: AsyncClient,
) -> None:
    """The host is named in the refusal, so the UI can ask about that host."""
    refused = await client.post("/llm/connections", json=REMOTE)
    assert refused.status_code == 403
    assert refused.json()["detail"]["destination"] == "host:api.provider.example"


async def test_stored_remote_connection_is_listed_off_and_refused(
    client: AsyncClient, engine: Engine
) -> None:
    """A connection allowed earlier and revoked later shows in the panel and is refused."""
    with create_session_factory(engine)() as session:
        session.add(ProviderConnection(**REMOTE))
        session.commit()

    assert (await _destinations(client))["host:api.provider.example"] == {
        "destination": "host:api.provider.example",
        "host": "api.provider.example",
        "enabled": False,
        "last_call_at": None,
    }
    assert (await client.get("/llm/connections/1/models")).status_code == 403


async def test_loopback_connections_are_not_egress(
    client: AsyncClient, openai_server: str
) -> None:
    """A provider on this machine needs no permission and has no panel row."""
    created = await client.post(
        "/llm/connections",
        json={**REMOTE, "label": "Local", "base_url": openai_server},
    )
    assert created.status_code == 201, created.text
    # The two weight downloads are always listed; the connection adds no third.
    assert set(await _destinations(client)) == {"ollama_pull", "image_model_pull"}


async def test_unknown_destination_is_rejected(client: AsyncClient) -> None:
    """Only destinations the app contacts can be toggled."""
    reply = await client.put("/egress/keygen", json={"enabled": True})
    assert reply.status_code == 422
