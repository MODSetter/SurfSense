"""A native ElevenLabs connection, end to end against a stub of its API."""

import io
import json
import sys
import threading
import wave
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import urlsplit

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.artifacts.podcast.brief import validate_options
from modules.llm import resolution
from modules.llm.connections import elevenlabs_router
from modules.llm.providers.elevenlabs.speech import ElevenLabsSpeech
from modules.llm.providers.protocols import SpokenTurn

pytestmark = pytest.mark.integration

GOOD_KEY = "good-key"
URL = "/llm/connections/elevenlabs"
MODELS = [
    {
        "model_id": "eleven_v4",
        "can_do_text_to_speech": True,
        "languages": [
            {"language_id": "en", "name": "English"},
            {"language_id": "de", "name": "German"},
        ],
    },
    {"model_id": "eleven_turbo_v2_5", "can_do_text_to_speech": True},
    {"model_id": "eleven_english_sts_v2", "can_do_text_to_speech": False},
]
VOICES = [
    {
        "voice_id": "talia-id",
        "name": "Talia",
        "category": "professional",
        "labels": {"gender": "female"},
    },
    {
        "voice_id": "george-id",
        "name": "George",
        "category": "premade",
        "labels": {"gender": "male"},
    },
    {
        "voice_id": "sarah-id",
        "name": "Sarah",
        "category": "premade",
        "labels": {"gender": "female"},
    },
]


def _wav() -> bytes:
    """A short clip as `wav_24000` answers."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x01\x00" * 100)
    return out.getvalue()


class StubElevenLabs(BaseHTTPRequestHandler):
    spoken: ClassVar[list[tuple[str, dict]]] = []
    missing: str | None = None
    voices: ClassVar[list[dict]] = VOICES
    # A status to answer the voice list with, as an outage or a revoked key would.
    voices_status: int | None = None

    def _answer(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _allowed(self) -> bool:
        if self.headers.get("xi-api-key") != GOOD_KEY:
            self._answer(401, {"detail": {"message": "Invalid API key"}})
            return False
        return True

    def do_GET(self) -> None:
        if not self._allowed():
            return
        path = urlsplit(self.path).path
        if path == self.missing:
            self._answer(
                401,
                {"detail": {"message": "The API key is missing the permission x."}},
            )
        elif path == "/v1/models":
            self._answer(200, MODELS)
        elif path == "/v2/voices" and self.voices_status:
            self._answer(self.voices_status, {"detail": {"message": "List refused."}})
        elif path == "/v2/voices":
            self._answer(200, {"voices": self.voices, "has_more": False})
        elif path == "/v1/user/subscription":
            self._answer(200, {"tier": "free"})
        else:
            self._answer(404, {"detail": "Not Found"})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not self._allowed():
            return
        type(self).spoken.append((self.path, body))
        audio = _wav()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def eleven(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The stub, standing where the connection's fixed address points."""
    StubElevenLabs.spoken = []
    StubElevenLabs.missing = None
    StubElevenLabs.voices = VOICES
    StubElevenLabs.voices_status = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubElevenLabs)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(elevenlabs_router, "API_URL", url)
    yield url
    server.shutdown()


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """A brief opens in a workspace."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def _connect(client: AsyncClient) -> dict:
    """A connection made with the key the stub accepts."""
    reply = await client.post(URL, json={"label": "My voices", "api_key": GOOD_KEY})
    assert reply.status_code == 201, reply.text
    return reply.json()


async def _choose(client: AsyncClient, connection: int, model: str = "eleven_v4"):
    """A model of the connection in the audio slot."""
    reply = await client.put(
        "/llm/selection/audio_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": connection,
            "name": model,
        },
    )
    assert reply.status_code == 200, reply.text


async def test_a_slot_is_told_elevenlabs_fills_audio_alone(client: AsyncClient) -> None:
    """Asked of the backend, as for a plan, so no picker decides it."""
    assert (await client.get(URL)).json() == {"serves": ["audio_gen"]}


async def test_a_good_key_connects_to_audio_alone_and_is_never_returned(
    client: AsyncClient, eleven: str
) -> None:
    """The key is stored, and no route gives it back."""
    saved = await _connect(client)

    assert saved["auth_kind"] == "elevenlabs"
    assert saved["base_url"] == eleven
    assert saved["has_api_key"] is True
    assert saved["serves"] == ["audio_gen"]
    assert GOOD_KEY not in json.dumps((await client.get("/llm/connections")).json())


async def test_a_bad_key_is_refused_in_elevenlabs_words_and_nothing_is_kept(
    client: AsyncClient, eleven: str
) -> None:
    """A failed check saves nothing, so no broken connection is left to fix."""
    reply = await client.post(URL, json={"label": "Mine", "api_key": "wrong"})

    assert reply.status_code == 422
    assert reply.json()["detail"] == {
        "code": "elevenlabs_refused",
        "message": "Invalid API key",
    }
    kept = (await client.get("/llm/connections")).json()
    assert [entry for entry in kept if entry["auth_kind"] == "elevenlabs"] == []


@pytest.mark.parametrize("path", ["/v1/models", "/v2/voices"])
async def test_a_key_missing_a_permission_is_told_which(
    client: AsyncClient, eleven: str, path: str
) -> None:
    """Without either list there is nothing to pick, though it could voice a line."""
    StubElevenLabs.missing = path

    reply = await client.post(URL, json={"label": "Mine", "api_key": GOOD_KEY})

    assert reply.status_code == 422
    assert "missing the permission" in reply.json()["detail"]["message"]


async def test_a_duplicate_name_is_refused(client: AsyncClient, eleven: str) -> None:
    """A name identifies a connection in every picker."""
    await _connect(client)

    reply = await client.post(URL, json={"label": "My voices", "api_key": GOOD_KEY})

    assert reply.status_code == 409


async def test_its_models_can_fill_audio_alone_with_the_voices_named(
    client: AsyncClient, eleven: str
) -> None:
    """Retired and non-speech models are not offered, nor a Free plan's refused voice."""
    saved = await _connect(client)

    listed = (await client.get(f"/llm/connections/{saved['id']}/models")).json()

    assert [model["name"] for model in listed] == ["eleven_v4"]
    assert listed[0]["selectable_for"] == ["audio_gen"]
    assert listed[0]["capability_source"] == "declared"
    assert listed[0]["voices"] == [
        {"id": "george-id", "label": "George"},
        {"id": "sarah-id", "label": "Sarah"},
    ]


async def test_it_cannot_fill_another_slot(client: AsyncClient, eleven: str) -> None:
    """Its API speaks, and nothing else."""
    saved = await _connect(client)

    chosen = await client.put(
        "/llm/selection/text_gen",
        json={
            "provider": "openai_compatible",
            "connection_id": saved["id"],
            "name": "eleven_v4",
            "allow_unlisted": True,
        },
    )

    assert chosen.status_code >= 400


async def test_a_line_is_tried_through_its_own_api(
    client: AsyncClient, eleven: str
) -> None:
    """Test voice reaches ElevenLabs route, not OpenAI's."""
    saved = await _connect(client)

    reply = await client.post(
        f"/llm/connections/{saved['id']}/speech-test",
        json={"model": "eleven_v4", "voice": "sarah-id", "prompt": "Hi."},
    )

    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"] == "audio/wav"
    path, body = StubElevenLabs.spoken[0]
    assert path == "/v1/text-to-speech/sarah-id?output_format=wav_24000"
    assert body == {"text": "Hi.", "model_id": "eleven_v4"}


async def test_trying_with_no_voice_says_to_choose_one(
    client: AsyncClient, eleven: str
) -> None:
    """It has no default voice, so nothing is sent or billed."""
    saved = await _connect(client)

    reply = await client.post(
        f"/llm/connections/{saved['id']}/speech-test",
        json={"model": "eleven_v4", "prompt": "Hi."},
    )

    assert reply.status_code == 502
    assert "voice" in reply.json()["detail"]
    assert StubElevenLabs.spoken == []


async def test_the_selection_lists_its_voices_by_name(
    client: AsyncClient, eleven: str
) -> None:
    """The ids are unreadable, so Settings shows the names."""
    saved = await _connect(client)
    await _choose(client, saved["id"])

    assert (await client.get("/llm/selection/audio_gen/voices")).json() == {
        "connection_id": saved["id"],
        "model": "eleven_v4",
        "source": "server",
        "voices": [
            {"id": "george-id", "label": "George"},
            {"id": "sarah-id", "label": "Sarah"},
        ],
        "added": [],
        "voices_page": None,
        "problem": None,
    }


async def test_a_brief_offers_usable_voices_by_gender_in_the_models_languages(
    client: AsyncClient, eleven: str, workspace_id: int
) -> None:
    """It must not open on a voice the plan refuses, or the script is written for
    nothing, nor on a language the model does not speak."""
    saved = await _connect(client)
    await _choose(client, saved["id"])

    opened = (
        await client.get(f"/workspaces/{workspace_id}/studio/podcast/brief")
    ).json()

    assert opened["voices_source"] == "server"
    assert opened["languages"] == ["en", "de"]
    assert opened["brief"]["language"] == "en"
    assert [s["voice"] for s in opened["brief"]["speakers"]] == [
        "george-id",
        "sarah-id",
    ]
    assert [(v["label"], v["gender"]) for v in opened["voices"]] == [
        ("George", "male"),
        ("Sarah", "female"),
    ]


async def test_a_podcast_voices_through_its_own_api(
    client: AsyncClient, eleven: str, engine: Engine
) -> None:
    """The job and the test share one rule for what voices a model."""
    saved = await _connect(client)
    await _choose(client, saved["id"])

    with Session(engine) as session:
        voice = resolution.resolve_text_to_speech(session)

    assert isinstance(voice, ElevenLabsSpeech)
    audio = await voice.synthesize([SpokenTurn("george-id", "Hi.")], "de")
    assert audio.media_type == "audio/wav"
    assert StubElevenLabs.spoken[-1][1]["language_code"] == "de"


async def test_editing_renames_keeps_the_address_and_takes_a_new_key_only_if_good(
    client: AsyncClient, eleven: str
) -> None:
    """A failed new key leaves the working connection as it was."""
    saved = await _connect(client)
    url = f"/llm/connections/{saved['id']}"
    write = {"label": "Renamed", "base_url": "https://elsewhere.example/v1"}

    renamed = await client.put(url, json=write)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["label"] == "Renamed"
    assert renamed.json()["base_url"] == eleven

    refused = await client.put(url, json={**write, "api_key": "wrong"})
    assert refused.status_code == 422
    # The working key still stands.
    assert (await client.get(f"{url}/models")).status_code == 200

    accepted = await client.put(url, json={**write, "api_key": GOOD_KEY})
    assert accepted.status_code == 200


async def test_disconnecting_clears_its_selection(
    client: AsyncClient, eleven: str
) -> None:
    """As any connection: the foreign key takes what it filled."""
    saved = await _connect(client)
    await _choose(client, saved["id"])

    assert (await client.delete(f"/llm/connections/{saved['id']}")).status_code == 204

    selection = await client.get("/llm/selection/audio_gen")
    assert selection.status_code == 404


VOICES_URL = "/llm/selection/audio_gen/voices"


async def test_an_account_with_no_usable_voices_says_so_and_can_add_one(
    client: AsyncClient, eleven: str, workspace_id: int
) -> None:
    """Not an empty list called the server's, which leaves nothing to do. A Free
    account made since March 2026 has no Default voices to list."""
    StubElevenLabs.voices = [VOICES[0]]
    saved = await _connect(client)
    await _choose(client, saved["id"])

    read = (await client.get(VOICES_URL)).json()

    assert read["source"] == "saved"
    assert read["voices"] == []
    assert read["problem"]["code"] == "no_usable_voices"
    opened = (
        await client.get(f"/workspaces/{workspace_id}/studio/podcast/brief")
    ).json()
    # What holds Generate and offers Set up voices.
    assert (opened["voices_source"], opened["voices"]) == ("saved", [])


async def test_a_refused_list_says_why_rather_than_that_none_are_listed(
    client: AsyncClient, eleven: str
) -> None:
    """A revoked key must show, so what was read before is not kept up."""
    saved = await _connect(client)
    await _choose(client, saved["id"])
    assert (await client.get(VOICES_URL)).json()["source"] == "server"

    StubElevenLabs.voices_status = 401
    read = (await client.get(VOICES_URL)).json()

    assert read["source"] == "saved"
    assert read["problem"] == {"code": "list_failed", "message": "List refused."}


async def test_an_outage_keeps_the_voices_already_read(
    client: AsyncClient, eleven: str
) -> None:
    """A brief failure says nothing about the voices, and Generate reads them too."""
    saved = await _connect(client)
    await _choose(client, saved["id"])
    before = (await client.get(VOICES_URL)).json()

    StubElevenLabs.voices_status = 503
    during = (await client.get(VOICES_URL)).json()

    assert during == before


async def test_an_outage_with_nothing_read_yet_says_so(
    client: AsyncClient, eleven: str, engine: Engine
) -> None:
    """Generate gives the real reason, not "add voices"."""
    saved = await _connect(client)
    StubElevenLabs.voices_status = 503
    await _choose(client, saved["id"])

    read = (await client.get(VOICES_URL)).json()

    assert read["source"] == "saved"
    assert read["problem"]["code"] == "list_failed"
    with Session(engine) as session, pytest.raises(ValueError, match="List refused"):
        validate_options(session, None)


async def test_a_list_that_cannot_be_read_is_a_502_not_a_crash(
    client: AsyncClient, eleven: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed reply reaches the model listing's usual failure."""
    saved = await _connect(client)
    monkeypatch.setattr(sys.modules[__name__], "MODELS", {"detail": "not a list"})

    reply = await client.get(f"/llm/connections/{saved['id']}/models")

    assert reply.status_code == 502
