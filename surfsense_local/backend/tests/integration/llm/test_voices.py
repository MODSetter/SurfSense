"""The voices a server's audio model offers podcasts: listed by the server,
or added by the user to the audio selection once each has been heard."""

import json

import pytest
from httpx import AsyncClient

from . import conftest
from .conftest import REMOTE_REQUESTS

pytestmark = pytest.mark.integration

URL = "/llm/selection/audio_gen/voices"


async def _choose(
    client: AsyncClient,
    base_url: str,
    model: str = "tts-1",
    catalog_provider: str = "custom",
) -> int:
    """A server's audio model in the audio slot; returns its connection id."""
    reply = await client.post(
        "/llm/connections",
        json={
            "label": f"Speech {model}",
            "provider": "openai_compatible",
            "base_url": base_url,
            "api_key": "secret",
            "catalog_provider": catalog_provider,
        },
    )
    assert reply.status_code == 201, reply.text
    connection = reply.json()["id"]
    await _select(client, connection, model)
    return connection


async def _select(client: AsyncClient, connection: int, model: str) -> None:
    chosen = await client.put(
        "/llm/selection/audio_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection,
            "name": model,
            "allow_unlisted": True,
        },
    )
    assert chosen.status_code == 200, chosen.text


async def test_a_server_that_lists_its_voices_offers_those(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asked of the server, as Kokoro-FastAPI answers; nothing to add."""
    monkeypatch.setattr(conftest, "AUDIO_VOICES", ["af_heart", "am_adam"])
    connection = await _choose(client, openai_server, "kokoro")

    assert (await client.get(URL)).json() == {
        "connection_id": connection,
        "model": "kokoro",
        "source": "server",
        "voices": ["af_heart", "am_adam"],
        "voices_page": None,
    }


async def test_a_voice_is_kept_only_once_the_server_has_voiced_it(
    client: AsyncClient, openai_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server that lists none takes the user's own: each heard before it is
    kept, so a podcast never meets a voice the server refuses."""
    monkeypatch.setattr(conftest, "REFUSED_VOICES", {"nobody"})
    connection = await _choose(client, openai_server)

    assert (await client.get(URL)).json() == {
        "connection_id": connection,
        "model": "tts-1",
        "source": "saved",
        "voices": [],
        "voices_page": None,
    }

    refused = await client.post(URL, json={"voice": "nobody"})
    assert refused.status_code == 502
    assert "unknown voice" in refused.json()["detail"]

    added = await client.post(URL, json={"voice": " alloy "})
    assert added.status_code == 201, added.text
    path, body = REMOTE_REQUESTS[-1]
    assert (path, json.loads(body)["voice"]) == ("/audio/speech", "alloy")
    assert (await client.post(URL, json={"voice": "alloy"})).status_code == 201
    await client.post(URL, json={"voice": "echo"})

    assert (await client.get(URL)).json()["voices"] == ["alloy", "echo"]

    removed = await client.delete(f"{URL}?voice=alloy")
    assert removed.status_code == 204
    assert (await client.get(URL)).json()["voices"] == ["echo"]


async def test_choosing_another_model_starts_its_voices_afresh(
    client: AsyncClient, openai_server: str
) -> None:
    """The voices belong to the model in the slot; another model has its own."""
    connection = await _choose(client, openai_server)
    await client.post(URL, json={"voice": "alloy"})

    await _select(client, connection, "tts-1")
    assert (await client.get(URL)).json()["voices"] == ["alloy"]
    await _select(client, connection, "tts-1-hd")
    assert (await client.get(URL)).json()["voices"] == []


async def test_openrouter_links_the_page_that_names_a_models_voices(
    client: AsyncClient, openai_server: str
) -> None:
    """OpenRouter lists no voices by API; its docs point to each model's page."""
    await _choose(
        client,
        openai_server,
        "bytedance-seed/seed-audio-1-0",
        catalog_provider="openrouter",
    )

    assert (await client.get(URL)).json()[
        "voices_page"
    ] == "https://openrouter.ai/bytedance-seed/seed-audio-1-0"


async def test_a_model_on_this_computer_has_no_server_voices(
    client: AsyncClient,
) -> None:
    """Its voices are its reviewed roster; nothing here is for it."""
    assert (await client.get(URL)).status_code == 409


async def test_a_removed_server_takes_its_voices_with_it(
    client: AsyncClient, openai_server: str
) -> None:
    """They go with the audio selection, which goes with its connection."""
    connection = await _choose(client, openai_server)
    await client.post(URL, json={"voice": "alloy"})

    await client.delete(f"/llm/connections/{connection}")
    await _choose(client, openai_server)

    assert (await client.get(URL)).json()["voices"] == []


async def test_a_voice_is_heard_in_the_line_it_is_given(
    client: AsyncClient, openai_server: str
) -> None:
    """The app sends the line in the interface's language, so the voice is
    heard speaking it; nothing says which languages a server's voice speaks."""
    await _choose(client, openai_server)

    await client.post(URL, json={"voice": "ff_siwis", "text": "Bonjour."})

    path, body = REMOTE_REQUESTS[-1]
    assert (path, json.loads(body)["input"]) == ("/audio/speech", "Bonjour.")
