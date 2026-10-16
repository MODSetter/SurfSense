"""The language the user says they speak, kept with the speech recognition
choice: `auto`, or one of the languages the chosen model is listed for."""

import pytest
from httpx import AsyncClient

from tests.integration.llm.installs import install_curated

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

ROUTE = "/llm/selection/speech_to_text/language"
NEMOTRON = "nemotron-3.5-asr-streaming-0.6b"
CANARY = "canary-180m-flash"


async def install(client: AsyncClient, model: str, **body: object) -> dict:
    """Install the recogniser's one build."""
    return await install_curated(client, model, "Q8_0", **body)


async def test_with_no_speech_model_there_is_no_language_to_read_or_set(
    client: AsyncClient, audio_dir
) -> None:
    """The intent belongs to a chosen model, so Settings is sent to choose one."""
    read = await client.get(ROUTE)
    written = await client.put(ROUTE, json={"language": "ja"})

    for reply in (read, written):
        assert reply.status_code == 409, reply.text
        assert reply.json()["detail"]["code"] == "needs_speech_model"


async def test_a_new_choice_detects_the_language_and_lists_what_it_offers(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Auto by default: Nemotron detects the language, and the select offers
    the 26 languages it is listed for."""
    await install(client, NEMOTRON, select=True)

    reply = await client.get(ROUTE)

    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["language"] == "auto"
    assert body["detects_language"] is True
    assert len(body["languages"]) == 26
    assert body["languages"][:3] == ["it", "es", "en"]


async def test_a_model_that_cannot_detect_starts_on_its_first_language(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Canary told nothing translates into English, so it is never told nothing:
    English, its first language, until another is set."""
    await install(client, CANARY, select=True)

    reply = await client.get(ROUTE)

    assert reply.status_code == 200, reply.text
    assert reply.json() == {
        "language": "en",
        "languages": ["en", "de", "fr"],
        "detects_language": False,
    }


async def test_a_model_that_cannot_detect_refuses_auto(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Settings offers no "Detect automatically" for it, so nothing sets it."""
    await install(client, CANARY, select=True)
    await client.put(ROUTE, json={"language": "de"})

    refused = await client.put(ROUTE, json={"language": "auto"})

    assert refused.status_code == 422, refused.text
    assert (await client.get(ROUTE)).json()["language"] == "de"


async def test_a_listed_language_is_kept_until_set_back_to_auto(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Kept with the choice, and never rewritten from what was detected."""
    await install(client, NEMOTRON, select=True)

    pinned = await client.put(ROUTE, json={"language": "ja"})

    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["language"] == "ja"
    assert (await client.get(ROUTE)).json()["language"] == "ja"

    back = await client.put(ROUTE, json={"language": "auto"})

    assert back.json()["language"] == "auto"
    assert (await client.get(ROUTE)).json()["language"] == "auto"


@pytest.mark.parametrize(
    "language",
    [
        pytest.param("et", id="one it only detects, at lower accuracy"),
        pytest.param("yue", id="one it does not know"),
        pytest.param("ja-JP", id="the family's locale, not a code"),
        pytest.param("", id="nothing"),
    ],
)
async def test_a_language_the_model_is_not_listed_for_is_refused(
    client: AsyncClient, audio_dir, fake_hub, language: str
) -> None:
    """The select offers only listed languages; anything else would reach the
    server as a locale it fails on or one it transcribes poorly."""
    await install(client, NEMOTRON, select=True)

    refused = await client.put(ROUTE, json={"language": language})

    assert refused.status_code == 422, refused.text
    assert (await client.get(ROUTE)).json()["language"] == "auto"


async def test_choosing_the_same_model_again_keeps_the_language(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Settings belong to the model, so only a different model drops them."""
    await install(client, NEMOTRON, select=True)
    await client.put(ROUTE, json={"language": "hi"})

    again = await client.put(
        "/llm/selection/speech_to_text",
        json={"provider": "audiocpp", "name": "nemotron-3.5-asr-streaming-0.6b-q8_0"},
    )

    assert again.status_code == 200, again.text
    assert (await client.get(ROUTE)).json()["language"] == "hi"


async def test_deleting_the_speech_model_takes_its_language_with_it(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The slot is cleared, and with it what was set for that model."""
    await install(client, NEMOTRON, select=True)
    await client.put(ROUTE, json={"language": "de"})

    await client.delete("/llm/models/nemotron-3.5-asr-streaming-0.6b-q8_0")

    assert (await client.get(ROUTE)).status_code == 409


async def test_the_chosen_model_resolves_with_its_reviewed_languages(
    client: AsyncClient, audio_dir, fake_hub, engine
) -> None:
    """What the transcription client will be built from: the installed file,
    the family the server dispatches on, and the entry's locales."""
    from modules.llm.resolution import resolve_speech_to_text
    from shared.db import create_session_factory

    await install(client, NEMOTRON, select=True)

    with create_session_factory(engine)() as session:
        resolved = resolve_speech_to_text(session)

    recogniser = resolved.recogniser
    assert recogniser.model_id == "nemotron-3.5-asr-streaming-0.6b-q8_0"
    assert recogniser.family == "nemotron_asr"
    assert recogniser.path == audio_dir / "nemotron-3.5-asr-streaming-0.6b-q8_0.gguf"
    assert recogniser.transcription.family_codes["ja"] == "ja-JP"
    assert recogniser.transcription.detected_only["et"] == "et-EE"
    assert resolved.selection.name == recogniser.model_id


async def test_with_no_speech_model_resolution_says_so(engine) -> None:
    """A distinct error, so the routes that need one answer needs_speech_model."""
    from modules.llm.resolution import NoSpeechModelError, resolve_speech_to_text
    from shared.db import create_session_factory

    with (
        create_session_factory(engine)() as session,
        pytest.raises(NoSpeechModelError),
    ):
        resolve_speech_to_text(session)
