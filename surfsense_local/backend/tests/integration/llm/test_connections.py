import asyncio
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from modules.llm.catalog.local.dependencies import get_local_catalog
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

    models = (await client.get(f"/llm/connections/{connection['id']}/models")).json()
    assert {model["name"] for model in models} == {
        "anthropic/claude-3.5-sonnet",
        "black-forest-labs/flux",
    }


async def test_listed_models_say_what_they_are_and_which_slots_they_fill(
    client: AsyncClient, openai_server: str
) -> None:
    """The listing speaks in model types, and the backend alone decides the slots."""
    connection = await _connect(client, openai_server)

    models = {
        model["name"]: model
        for model in (
            await client.get(f"/llm/connections/{connection['id']}/models")
        ).json()
    }

    chat = models["anthropic/claude-3.5-sonnet"]
    image = models["black-forest-labs/flux"]
    assert (chat["types"], chat["selectable_for"]) == (["text_gen"], ["text_gen"])
    assert (image["types"], image["selectable_for"]) == (["image_gen"], ["image_gen"])


async def test_a_model_nothing_recognises_can_fill_every_slot(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown is not no: the user sees it answer before trusting it anywhere."""
    monkeypatch.setattr(
        conftest,
        "REMOTE_MODELS",
        [*conftest.REMOTE_MODELS, {"id": "acme/mystery-1"}],
    )
    connection = await _connect(client, openai_server)

    models = (await client.get(f"/llm/connections/{connection['id']}/models")).json()
    mystery = next(model for model in models if model["name"] == "acme/mystery-1")

    assert mystery["types"] == []
    assert mystery["capability_source"] == "unknown"
    assert mystery["selectable_for"] == [
        "text_gen",
        "image_gen",
        "image_edit",
        "video_gen",
        "audio_gen",
    ]


async def test_a_declared_video_model_fills_the_video_slot_and_nothing_else(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every type is a slot the user can fill, even one no feature reads yet."""
    monkeypatch.setattr(
        conftest,
        "REMOTE_MODELS",
        [
            *conftest.REMOTE_MODELS,
            {"id": "acme/clipmaker", "architecture": {"output_modalities": ["video"]}},
        ],
    )
    connection = await _connect(client, openai_server)
    choice = {
        "provider": "openai_compatible",
        "connection_id": connection["id"],
        "name": "acme/clipmaker",
    }

    chosen = await client.put("/llm/selection/video_gen", json=choice)
    refused = await client.put("/llm/selection/text_gen", json=choice)

    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["model_type"] == "video_gen"
    assert refused.status_code == 422


async def test_a_catalogued_embedder_fills_no_slot(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The manifest keeps the evidence the classifier needs, so an embedder the
    endpoint lists without modalities is known to be no chat model."""
    monkeypatch.setattr(
        conftest,
        "REMOTE_MODELS",
        [*conftest.REMOTE_MODELS, {"id": "text-embedding-3-small"}],
    )
    connection = await _connect(client, openai_server)

    models = (await client.get(f"/llm/connections/{connection['id']}/models")).json()
    embedder = next(m for m in models if m["name"] == "text-embedding-3-small")

    assert embedder["capability_source"] == "catalog"
    assert (embedder["types"], embedder["selectable_for"]) == ([], [])


async def test_a_connection_names_the_manifest_provider_it_reaches(
    client: AsyncClient, openai_server: str
) -> None:
    """Stored as chosen, never read back from the URL; omitted means custom."""
    body = {"provider": "openai_compatible", "base_url": openai_server}
    named = await client.post(
        "/llm/connections", json={**body, "label": "Neon", "catalog_provider": "neon"}
    )
    plain = await client.post("/llm/connections", json={**body, "label": "Mine"})

    assert named.json()["catalog_provider"] == "neon"
    assert plain.json()["catalog_provider"] == "custom"
    listed = {
        c["label"]: c["catalog_provider"]
        for c in (await client.get("/llm/connections")).json()
    }
    assert listed == {"Neon": "neon", "Mine": "custom"}


async def test_a_provider_the_manifest_does_not_list_is_refused_before_saving(
    client: AsyncClient, openai_server: str
) -> None:
    """A typo would otherwise scope every lookup to nothing."""
    refused = await client.post(
        "/llm/connections",
        json={
            "label": "Typo",
            "provider": "openai_compatible",
            "base_url": openai_server,
            "catalog_provider": "opneai",
        },
    )

    assert refused.status_code == 422
    assert (await client.get("/llm/connections")).json() == []


async def test_a_connection_reads_its_own_providers_entry(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neon serves gpt-5-5 with image output; other providers serve it as text.
    A Neon connection reads Neon's entry, a custom one what every provider agrees on."""
    monkeypatch.setattr(
        conftest, "REMOTE_MODELS", [*conftest.REMOTE_MODELS, {"id": "gpt-5-5"}]
    )
    body = {"provider": "openai_compatible", "base_url": openai_server}
    neon = (
        await client.post(
            "/llm/connections",
            json={**body, "label": "Neon", "catalog_provider": "neon"},
        )
    ).json()
    custom = (
        await client.post("/llm/connections", json={**body, "label": "Mine"})
    ).json()

    async def types(connection: dict) -> list[str]:
        listed = (
            await client.get(f"/llm/connections/{connection['id']}/models")
        ).json()
        return next(m["types"] for m in listed if m["name"] == "gpt-5-5")

    assert await types(neon) == ["text_gen", "image_gen", "image_edit"]
    assert await types(custom) == ["text_gen"]


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
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection["id"],
            "name": "anthropic/claude-3.5-sonnet",
        },
    )
    image = await client.put(
        "/llm/selection/image_gen",
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
        "/llm/selection/text_gen",
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
    assert (await client.get("/llm/selection/text_gen")).status_code == 404


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


SD15 = "v1-5-pruned_Q4_0"
SDXL = "sd_xl_base_1.0_0_Q4_0"


def _stage(directory: Path, monkeypatch: pytest.MonkeyPatch, *ids: str) -> None:
    """A build that ships sd-server, with these curated builds on disk under
    their own names, as a file copied in by hand would be."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", directory)
    get_local_catalog.cache_clear()
    for model_id in ids:
        (directory / f"{model_id}.gguf").write_bytes(b"GGUF")


async def test_the_local_image_model_can_take_the_image_role(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It carries no connection, which selected_models must permit."""
    _stage(tmp_path, monkeypatch, SDXL)

    chosen = await client.put(
        "/llm/selection/image_gen",
        json={"provider": sdcpp.PROVIDER, "connection_id": None, "name": SDXL},
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["provider"] == sdcpp.PROVIDER

    read = await client.get("/llm/selection/image_gen")
    assert read.json()["name"] == SDXL


async def test_an_image_model_that_is_not_installed_cannot_be_chosen(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sd-server would be started pointing at nothing."""
    _stage(tmp_path, monkeypatch)

    refused = await client.put(
        "/llm/selection/image_gen",
        json={"provider": sdcpp.PROVIDER, "connection_id": None, "name": SD15},
    )

    assert refused.status_code == 422


async def test_image_model_downloads_are_listed_and_refusable_too(
    client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weights come from huggingface.co, so Network must name it and hold it off."""
    _stage(tmp_path, monkeypatch)

    listed = (await client.get("/egress")).json()
    row = next(d for d in listed if d["destination"] == "host:huggingface.co")
    assert row["host"] == "huggingface.co"
    assert row["enabled"] is False

    rows = (await client.get("/llm/catalog/local")).json()["rows"]
    sd15 = next(r for r in rows if r["id"] == "stable-diffusion-1.5")
    denied = await client.post(
        "/llm/installs", json={"catalog_id": sd15["builds"][0]["catalog_id"]}
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["destination"] == "host:huggingface.co"


async def test_image_selection_alone_does_not_complete_onboarding(
    client: AsyncClient, openai_server: str
) -> None:
    """The optional Image role cannot bypass required chat onboarding."""
    connection = await _connect(client, openai_server)
    selected = await client.put(
        "/llm/selection/image_gen",
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
        ("text_gen", "anthropic/claude-3.5-sonnet"),
        ("image_gen", "black-forest-labs/flux"),
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
    assert (await client.get("/llm/selection/text_gen")).status_code == 404
    assert (await client.get("/llm/selection/image_gen")).status_code == 404
    assert (await client.get("/llm/onboarding")).json() == {"completed": True}


async def test_unverified_and_unlisted_paths_require_explicit_confirmation(
    client: AsyncClient,
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
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": saved.json()["id"],
            "name": "manual-model",
        },
    )
    assert ordinary.status_code == 422
    confirmed = await client.put(
        "/llm/selection/text_gen",
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


def _closed_port() -> int:
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.mark.parametrize(
    ("answered", "code"),
    [
        (401, "provider_auth"),
        (403, "provider_auth"),
        (429, "provider_rate_limited"),
        (503, "provider_error"),
    ],
)
async def test_a_failed_model_listing_names_what_the_provider_answered(
    client: AsyncClient, openai_server: str, answered: int, code: str
) -> None:
    """Startup and Settings say why a model is unusable, not only that it is."""
    connection = await _connect(client, openai_server)
    conftest.MODELS_STATUS = answered

    listed = await client.get(f"/llm/connections/{connection['id']}/models")

    assert listed.status_code == 502
    assert listed.json()["detail"]["code"] == code


async def test_an_unreachable_provider_is_named_as_unreachable(
    client: AsyncClient, openai_server: str, engine
) -> None:
    """Offline, or the endpoint gone, is told apart from a refused key."""
    connection = await _connect(client, openai_server)
    # The endpoint goes away after it was saved, as an offline machine sees it.
    from sqlalchemy import update

    from modules.llm.models import ProviderConnection
    from shared.db import create_session_factory

    with create_session_factory(engine)() as session:
        session.execute(
            update(ProviderConnection)
            .where(ProviderConnection.id == connection["id"])
            .values(base_url=f"http://127.0.0.1:{_closed_port()}")
        )
        session.commit()

    listed = await client.get(f"/llm/connections/{connection['id']}/models")

    assert listed.status_code == 502
    assert listed.json()["detail"]["code"] == "provider_unreachable"
