"""The remote catalog over HTTP: providers first, a provider's rows when opened."""

import socket

import pytest
from httpx import AsyncClient

from modules.llm.catalog.remote.manifest.loader import load_remote_manifest

pytestmark = pytest.mark.integration


async def _connection(client: AsyncClient, base_url: str, **fields: object) -> dict:
    reply = await client.post(
        "/llm/connections",
        json={"label": "Work", "provider": "openai_compatible", "base_url": base_url, **fields},
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def test_providers_come_with_their_type_counts_and_connections(
    client: AsyncClient, openai_server: str
) -> None:
    """Small enough to paint first; a provider's rows come when it is opened."""
    await _connection(client, openai_server, catalog_provider="openai")

    providers = {p["id"]: p for p in (await client.get("/llm/catalog/remote")).json()}

    openai = providers["openai"]
    assert openai["connect"]["status"] == "ready"
    assert openai["type_counts"]["text_gen"] > 0
    assert openai["connections"] == 1
    assert providers["groq"]["connections"] == 0


async def test_a_providers_rows_say_whether_a_key_is_missing_or_unchecked(
    client: AsyncClient, openai_server: str
) -> None:
    """Offline: nothing here calls the endpoint."""
    before = (await client.get("/llm/catalog/remote/providers/openai")).json()
    await _connection(client, openai_server, catalog_provider="openai")
    after = (await client.get("/llm/catalog/remote/providers/openai")).json()

    assert {row["availability"] for row in before} == {"not_connected"}
    assert {row["availability"] for row in after} <= {"unchecked", "unusable"}
    assert {row["connection"]["label"] for row in after if row["connection"]} == {"Work"}


async def test_deprecated_models_are_hidden_unless_asked_for(client: AsyncClient) -> None:
    """Still in the manifest, so a selection that uses one can say why it stopped."""
    provider = next(
        name
        for name, entry in load_remote_manifest().providers.items()
        if any(model.status == "deprecated" for model in entry.models.values())
    )
    url = f"/llm/catalog/remote/providers/{provider}"

    shown = (await client.get(url)).json()
    everything = (await client.get(url, params={"include_deprecated": True})).json()

    assert all(row["status"] != "deprecated" for row in shown)
    assert len(everything) > len(shown)


async def test_an_unknown_provider_is_a_404(client: AsyncClient) -> None:
    """A path names a provider the manifest does not have."""
    assert (await client.get("/llm/catalog/remote/providers/opneai")).status_code == 404


async def test_a_connection_checks_the_manifest_against_its_live_listing(
    client: AsyncClient, openai_server: str
) -> None:
    """What the key serves is available, what it does not is not served, and what
    the manifest has not heard of yet still shows up."""
    connection = await _connection(client, openai_server, catalog_provider="openai")

    rows = (await client.get(f"/llm/catalog/remote/connections/{connection['id']}")).json()
    by_model = {row["model_id"]: row for row in rows}

    assert by_model["gpt-5-nano"]["availability"] == "not_served"
    assert by_model["anthropic/claude-3.5-sonnet"]["availability"] == "available"


async def test_an_endpoint_that_is_down_leaves_its_rows_unchecked_not_gone(
    client: AsyncClient,
) -> None:
    """A down endpoint is not the models disappearing, so this is not a 502."""
    connection = await _connection(
        client,
        f"http://127.0.0.1:{_closed_port()}/v1",
        catalog_provider="openai",
        allow_unverified=True,
    )

    reply = await client.get(f"/llm/catalog/remote/connections/{connection['id']}")

    assert reply.status_code == 200
    assert {row["availability"] for row in reply.json()} <= {"could_not_check", "unusable"}
