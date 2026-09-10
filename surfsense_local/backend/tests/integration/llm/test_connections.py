import pytest
from httpx import AsyncClient

from modules.llm.providers.openai_compatible import OpenAICompatibleChatProvider
from modules.llm.providers.types import Message

pytestmark = pytest.mark.integration


async def _connect(client: AsyncClient, base_url: str, label: str = "Internal"):
    reply = await client.post(
        "/llm/connections",
        json={
            "label": label,
            "provider": "openai_compatible",
            "base_url": base_url,
            "api_key": "secret",
        },
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


async def test_connection_secret_is_redacted_and_models_merge(
    client: AsyncClient, openai_server: str
) -> None:
    """One card exposes live text and image models without exposing its key."""
    connection = await _connect(client, openai_server)

    listed = await client.get("/llm/connections")
    assert listed.json()[0]["has_api_key"] is True
    assert "secret" not in listed.text

    models = (
        await client.get(f"/llm/connections/{connection['id']}/models")
    ).json()
    assert {model["name"] for model in models} == {
        "anthropic/claude-3.5-sonnet",
        "black-forest-labs/flux",
    }


async def test_connection_update_distinguishes_omitted_and_null_secret(
    client: AsyncClient, openai_server: str
) -> None:
    """Editing metadata preserves a secret; explicit null removes it."""
    connection = await _connect(client, openai_server)
    endpoint = f"/llm/connections/{connection['id']}"
    common = {
        "label": "Renamed",
        "provider": "openai_compatible",
        "base_url": openai_server,
    }
    preserved = await client.put(endpoint, json=common)
    assert preserved.json()["has_api_key"] is True
    cleared = await client.put(endpoint, json={**common, "api_key": None})
    assert cleared.json()["has_api_key"] is False


async def test_openai_compatible_chat_streams_standard_deltas(
    openai_server: str,
) -> None:
    """A connection-backed generator speaks portable chat completions."""
    provider = OpenAICompatibleChatProvider(openai_server, "secret")
    deltas = [
        delta
        async for delta in provider.chat(
            "anthropic/claude-3.5-sonnet",
            [Message(role="user", content="hello")],
        )
    ]
    assert "".join(deltas) == "Hello"


async def test_chat_and_image_roles_can_use_one_connection(
    client: AsyncClient, openai_server: str
) -> None:
    """A gateway connection may back both independent selected roles."""
    connection = await _connect(client, openai_server)
    chat = await client.put(
        "/llm/selection/generation",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "anthropic/claude-3.5-sonnet",
        },
    )
    image = await client.put(
        "/llm/selection/image_generation",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "black-forest-labs/flux",
        },
    )
    assert chat.status_code == 200
    assert image.status_code == 200
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}

    tested = await client.post(
        f"/llm/connections/{connection['id']}/image-test",
        json={"model": "black-forest-labs/flux"},
    )
    assert tested.status_code == 200
    assert tested.headers["content-type"] == "image/png"
    assert tested.headers["cache-control"] == "no-store"


async def test_image_selection_alone_does_not_complete_onboarding(
    client: AsyncClient, openai_server: str
) -> None:
    """The optional Image role cannot bypass required chat onboarding."""
    connection = await _connect(client, openai_server)
    selected = await client.put(
        "/llm/selection/image_generation",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "black-forest-labs/flux",
        },
    )
    assert selected.status_code == 200
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}


async def test_deleting_connection_cascades_only_its_selections(
    client: AsyncClient, openai_server: str
) -> None:
    """Disconnect removes both referenced roles but preserves onboarding."""
    connection = await _connect(client, openai_server)
    for role, name in (
        ("generation", "anthropic/claude-3.5-sonnet"),
        ("image_generation", "black-forest-labs/flux"),
    ):
        await client.put(
            f"/llm/selection/{role}",
            json={
                "provider": "openai_compatible",
                "connection_id": connection["id"],
                "name": name,
            },
        )

    assert (
        await client.delete(f"/llm/connections/{connection['id']}")
    ).status_code == 204
    assert (await client.get("/llm/selection/generation")).status_code == 404
    assert (
        await client.get("/llm/selection/image_generation")
    ).status_code == 404
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}


async def test_unverified_and_unlisted_paths_require_explicit_confirmation(
    client: AsyncClient
) -> None:
    """Network and catalogue bypasses never happen from an ordinary save."""
    body = {
        "label": "Offline gateway",
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:9/v1",
    }
    assert (await client.post("/llm/connections", json=body)).status_code == 422
    saved = await client.post(
        "/llm/connections", json={**body, "allow_unverified": True}
    )
    assert saved.status_code == 201

    ordinary = await client.put(
        "/llm/selection/generation",
        json={
            "provider": "openai_compatible",
            "connection_id": saved.json()["id"],
            "name": "manual-model",
        },
    )
    assert ordinary.status_code == 422
    confirmed = await client.put(
        "/llm/selection/generation",
        json={
            "provider": "openai_compatible",
            "connection_id": saved.json()["id"],
            "name": "manual-model",
            "allow_unlisted": True,
        },
    )
    assert confirmed.status_code == 200
