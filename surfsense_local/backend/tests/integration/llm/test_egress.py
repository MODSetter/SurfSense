"""Nothing leaves the machine until the user allows that destination."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.models import ProviderConnection
from shared.config import get_llm_settings
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
    # huggingface.co is always listed; the connection adds no second row.
    assert set(await _destinations(client)) == {"host:huggingface.co"}


async def test_unknown_destination_is_rejected(client: AsyncClient) -> None:
    """Only destinations the app contacts can be toggled."""
    reply = await client.put("/egress/keygen", json={"enabled": True})
    assert reply.status_code == 422


async def test_one_grant_covers_everything_sent_to_huggingface(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three calls, one host, one row in the panel. Searching, downloading
    weights and downloading an image model all reach huggingface.co, so the
    question the user is asked is about the host and is asked once.
    """
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", tmp_path)
    get_local_catalog.cache_clear()
    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    catalog_id = rows[0]["builds"][0]["catalog_id"]
    image_id = next(r for r in rows if r["engine"] == "sdcpp")["builds"][0][
        "catalog_id"
    ]

    refusals = [
        await client.get("/llm/catalog/local/search", params={"q": "qwen"}),
        await client.post("/llm/install", json={"catalog_id": catalog_id}),
        await client.post("/llm/install", json={"catalog_id": image_id}),
    ]

    assert [refused.status_code for refused in refusals] == [403, 403, 403]
    assert {refused.json()["detail"]["destination"] for refused in refusals} == {
        "host:huggingface.co"
    }
