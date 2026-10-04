"""Nothing leaves the machine until the user allows that destination."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, select

from modules.egress.models import EgressDestination
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.resolution import resolve_image_generation
from shared.config import get_llm_settings
from shared.db import create_session_factory

from . import conftest

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
        await client.post("/llm/installs", json={"catalog_id": catalog_id}),
        await client.post("/llm/installs", json={"catalog_id": image_id}),
    ]

    assert [refused.status_code for refused in refusals] == [403, 403, 403]
    assert {refused.json()["detail"]["destination"] for refused in refusals} == {
        "host:huggingface.co"
    }


def _store(engine: Engine, *connections: dict) -> None:
    with create_session_factory(engine)() as session:
        session.add_all(ProviderConnection(**connection) for connection in connections)
        session.commit()


async def _allow(client: AsyncClient, destination: str) -> None:
    reply = await client.put(f"/egress/{destination}", json={"enabled": True})
    assert reply.status_code == 200, reply.text


async def test_deleting_one_of_two_connections_to_a_host_keeps_its_grant(
    client: AsyncClient, engine: Engine
) -> None:
    """The other connection is still there, and the user still consented to it."""
    _store(engine, REMOTE, {**REMOTE, "label": "Cloud images"})
    await _allow(client, "host:api.provider.example")

    assert (await client.delete("/llm/connections/1")).status_code == 204

    assert (await _destinations(client))["host:api.provider.example"]["enabled"]


async def test_deleting_the_last_connection_to_a_host_withdraws_its_grant(
    client: AsyncClient, engine: Engine
) -> None:
    """A later connection to the same host asks again instead of inheriting it."""
    _store(engine, REMOTE)
    await _allow(client, "host:api.provider.example")

    assert (await client.delete("/llm/connections/1")).status_code == 204

    assert set(await _destinations(client)) == {"host:huggingface.co"}
    refused = await client.post("/llm/connections", json=REMOTE)
    assert refused.status_code == 403
    assert refused.json()["detail"]["destination"] == "host:api.provider.example"


async def test_deleting_a_loopback_connection_touches_no_grant(
    client: AsyncClient, openai_server: str
) -> None:
    """A provider on this machine had no destination, so none is left behind."""
    created = await client.post(
        "/llm/connections",
        json={**REMOTE, "label": "Local", "base_url": openai_server},
    )
    assert created.status_code == 201, created.text

    deleted = await client.delete(f"/llm/connections/{created.json()['id']}")

    assert deleted.status_code == 204
    assert set(await _destinations(client)) == {"host:huggingface.co"}


async def test_deleting_a_connection_to_huggingface_keeps_the_built_in_grant(
    client: AsyncClient, engine: Engine
) -> None:
    """Model downloads reach huggingface.co with or without a connection there."""
    _store(engine, {**REMOTE, "base_url": "https://huggingface.co/v1"})
    await _allow(client, "host:huggingface.co")

    assert (await client.delete("/llm/connections/1")).status_code == 204

    assert (await _destinations(client))["host:huggingface.co"]["enabled"]


async def _image_test(client: AsyncClient, base_url: str):
    created = await client.post(
        "/llm/connections", json={**REMOTE, "label": "Local", "base_url": base_url}
    )
    assert created.status_code == 201, created.text
    return await client.post(
        f"/llm/connections/{created.json()['id']}/image-test",
        json={"model": "black-forest-labs/flux"},
    )


async def test_an_image_url_on_a_host_nobody_allowed_is_refused_and_listed(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint chose the host, so the user is asked about it by name."""
    monkeypatch.setattr(conftest, "IMAGE_URL", "https://cdn.provider.example/x.png")

    reply = await _image_test(client, openai_server)

    assert reply.status_code == 403
    assert reply.json()["detail"]["code"] == "egress_disabled"
    assert reply.json()["detail"]["host"] == "cdn.provider.example"
    listed = await _destinations(client)
    assert listed["host:cdn.provider.example"]["enabled"] is False


async def test_an_image_url_on_loopback_needs_no_decision(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bundled sd-server serves its own files; that never leaves the machine."""
    monkeypatch.setattr(conftest, "IMAGE_URL", f"{openai_server}/missing.png")

    reply = await _image_test(client, openai_server)

    # Reached the stub, which has no such file: fetched, not refused.
    assert reply.status_code == 502
    assert "host:127.0.0.1" not in await _destinations(client)


async def test_a_studio_image_on_an_unallowed_host_fails_without_retrying(
    engine: Engine, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No dialog reaches the worker, and a retry would pay for the image again."""
    monkeypatch.setattr(conftest, "IMAGE_URL", "https://cdn.provider.example/x.png")
    _store(engine, {**REMOTE, "label": "Local", "base_url": openai_server})
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.IMAGE_GEN,
                provider="openai_compatible",
                connection_id=1,
                name="black-forest-labs/flux",
            )
        )
        session.commit()
        resolved = resolve_image_generation(session)

        with pytest.raises(NonRetryableImageError, match=r"cdn\.provider\.example"):
            await resolved.generator.generate("black-forest-labs/flux", "draw")

    with create_session_factory(engine)() as session:
        destinations = [
            row.destination for row in session.scalars(select(EgressDestination))
        ]
    assert destinations == ["host:cdn.provider.example"]
