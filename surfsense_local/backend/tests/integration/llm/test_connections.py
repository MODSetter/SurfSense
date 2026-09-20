import asyncio
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.connections.router import CHAT_TEST_MAX_TOKENS
from modules.llm.providers.openai_compatible import OpenAICompatibleChatProvider
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.providers.types import Message
from shared.config import get_llm_settings

from . import conftest
from .conftest import REMOTE_REQUESTS

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


async def test_model_discovery_does_not_hold_the_write_lock(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow remote probe must not stall the app: the handler ends its
    transaction before the network call, so another request writes meanwhile."""
    connection = await _connect(client, openai_server)
    probing, answered = asyncio.Event(), asyncio.Event()

    async def slow_discovery(_connection: object) -> list:
        probing.set()
        await answered.wait()
        return []

    monkeypatch.setattr(
        "modules.llm.connections.router.discover_models", slow_discovery
    )
    discovery = asyncio.create_task(
        client.get(f"/llm/connections/{connection['id']}/models")
    )
    await probing.wait()

    # Were the lock still held, this would wait out busy_timeout (5s) and fail.
    written = await asyncio.wait_for(
        client.post("/workspaces", json={"name": "meanwhile"}), timeout=2
    )
    assert written.status_code == 201
    answered.set()
    assert (await discovery).status_code == 200


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
    assert (await client.get("/llm/onboarding")).json() == {"completed": False}
    assert (await client.post("/llm/onboarding")).status_code == 200
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}

    tested = await client.post(
        f"/llm/connections/{connection['id']}/image-test",
        json={"model": "black-forest-labs/flux"},
    )
    assert tested.status_code == 200
    assert tested.headers["content-type"] == "image/png"
    assert tested.headers["cache-control"] == "no-store"


async def test_a_hosted_models_tier_is_read_from_the_listing_it_came_from(
    client: AsyncClient, openai_server: str
) -> None:
    """A closed line states no size anywhere, so only the listing places it."""
    connection = await _connect(client, openai_server)

    selected = await client.put(
        "/llm/selection/generation",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "anthropic/claude-3.5-sonnet",
        },
    )

    assert selected.json()["tier"] == "frontier"


async def test_chat_test_answers_without_selecting_or_running_up_a_bill(
    client: AsyncClient, openai_server: str
) -> None:
    """Most endpoints never say which models chat, so let one answer and show it."""
    connection = await _connect(client, openai_server)

    tested = await client.post(
        f"/llm/connections/{connection['id']}/chat-test",
        json={"model": "anthropic/claude-3.5-sonnet"},
    )
    assert tested.status_code == 200
    assert tested.json() == {"reply": "Hello"}

    path, body = REMOTE_REQUESTS[-1]
    assert path == "/chat/completions"
    # Only a model that spends the budget thinking ever reaches this cap: the
    # reply is cut at its character limit as soon as text arrives, so a plain
    # answer costs the same handful of tokens it always did.
    assert json.loads(body)["max_tokens"] == CHAT_TEST_MAX_TOKENS

    # Trying a model is not choosing it.
    assert (await client.get("/llm/selection/generation")).status_code == 404


async def test_a_thinking_model_on_a_connection_is_not_called_broken(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It answers, after a trace longer than the old 64 token cap allowed.

    A remote endpoint cannot be told to stop thinking, so the budget is what
    decides whether the user is shown the answer or told their working model
    replied with nothing.
    """
    monkeypatch.setattr(conftest, "REMOTE_THINKS", True)
    connection = await _connect(client, openai_server)

    tested = await client.post(
        f"/llm/connections/{connection['id']}/chat-test",
        json={"model": "anthropic/claude-3.5-sonnet"},
    )

    assert tested.status_code == 200
    assert tested.json() == {"reply": "Hello"}


def _stage(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> sdcpp.ImageModel:
    """Point the catalogue at a temp dir and download its first entry, small."""
    from dataclasses import replace

    monkeypatch.setattr(get_llm_settings(), "image_models_dir", directory)
    monkeypatch.setattr(
        sdcpp,
        "CATALOG",
        tuple(replace(model, size_bytes=2048) for model in sdcpp.CATALOG),
    )
    model = sdcpp.CATALOG[0]
    (directory / model.file).write_bytes(b"\0" * model.size_bytes)
    return model


async def test_the_local_image_model_can_take_the_image_role(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It carries no connection, which selected_models must permit."""
    model = _stage(tmp_path, monkeypatch)

    chosen = await client.put(
        "/llm/selection/image_generation",
        json={
            "provider": sdcpp.PROVIDER,
            "connection_id": None,
            "name": model.name,
        },
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["provider"] == sdcpp.PROVIDER

    read = await client.get("/llm/selection/image_generation")
    assert read.json()["name"] == model.name

    # Electron reconciles sd-server against this, so it must name the weights
    # and the flags the chosen model needs.
    runtime = (await client.get("/llm/image/local/runtime")).json()
    assert runtime["file"] == model.file
    assert runtime["args"] == list(model.args)


async def test_an_image_model_in_use_cannot_be_deleted_out_from_under_itself(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting the chosen weights would leave sd-server pointed at nothing."""
    model = _stage(tmp_path, monkeypatch)
    spare = sdcpp.CATALOG[1]
    (tmp_path / spare.file).write_bytes(b"\0" * spare.size_bytes)

    await client.put(
        "/llm/selection/image_generation",
        json={
            "provider": sdcpp.PROVIDER,
            "connection_id": None,
            "name": model.name,
        },
    )

    refused = await client.delete(f"/llm/image/local/{model.name}")
    assert refused.status_code == 409
    assert (tmp_path / model.file).is_file()

    # One that holds no role goes without argument.
    removed = await client.delete(f"/llm/image/local/{spare.name}")
    assert removed.status_code == 204
    assert not (tmp_path / spare.file).exists()

    listed = (await client.get("/llm/image/local")).json()["models"]
    assert {m["name"]: m["installed"] for m in listed}[spare.name] is False


async def test_local_image_model_is_silent_on_a_host_without_sd_server(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No staged binary means no models dir: say so, and refuse the download."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", None)

    read = await client.get("/llm/image/local")
    assert read.status_code == 200
    body = read.json()
    assert body["offered"] is False
    assert body["ready"] is False
    assert body["provider"] == "sdcpp"
    assert all(model["installed"] is False for model in body["models"])

    refused = await client.post(
        f"/llm/image/local/{sdcpp.CATALOG[0].name}/install"
    )
    assert refused.status_code == 409


async def test_image_model_downloads_are_listed_and_refusable_too(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weights come from huggingface.co, so Network must name it and hold it off."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", tmp_path)

    listed = (await client.get("/egress")).json()
    row = next(d for d in listed if d["destination"] == "image_model_pull")
    assert row["host"] == "huggingface.co"
    assert row["enabled"] is False

    denied = await client.post(
        f"/llm/image/local/{sdcpp.CATALOG[0].name}/install"
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["destination"] == "image_model_pull"


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
    assert (await client.post("/llm/onboarding")).status_code == 200

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


async def test_a_key_the_app_can_no_longer_read_is_explained_not_a_crash(
    client: AsyncClient, openai_server: str, engine
) -> None:
    """Reachable without tampering, so it cannot answer with a stack trace.

    The per install secret lives in the OS keychain. A keychain reset, or a
    backup restored onto another machine, leaves every stored key
    undecryptable. The key is gone either way; the only thing left to decide is
    whether the app says so or returns an Internal Server Error and leaves the
    connection list broken with no route to recovery.
    """
    connection = await _connect(client, openai_server)
    row = await client.get("/llm/connections")
    assert row.status_code == 200

    # Damage the stored ciphertext exactly as a changed secret would.
    from sqlalchemy import update

    from modules.llm.models import ProviderConnection
    from shared.db import create_session_factory

    with create_session_factory(engine)() as session:
        session.execute(
            update(ProviderConnection)
            .where(ProviderConnection.id == connection["id"])
            .values(api_key_ciphertext=b"not-a-token-this-key-changed")
        )
        session.commit()

    listed = await client.get(f"/llm/connections/{connection['id']}/models")

    assert listed.status_code != 500
    detail = listed.json()["detail"]
    assert detail["code"] == "unreadable_secret"
    assert "key" in detail["message"].casefold()
