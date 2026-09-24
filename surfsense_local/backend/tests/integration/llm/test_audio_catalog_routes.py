"""Audio models in the one local catalog, offered by audio.cpp, and the
`server.json` Electron starts audio.cpp's server from."""

import json

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AUDIO_IDS = {"kokoro-82m", "supertonic-3", "kitten-tts-mini-0.8"}


def audio_rows(body: dict) -> dict[str, dict]:
    """The rows audio.cpp offered, by id."""
    return {r["id"]: r for r in body["rows"] if r["engine"] == "audiocpp"}


async def test_audio_models_are_rows_with_no_fit_claim(
    client: AsyncClient, audio_dir
) -> None:
    """Runnable, downloadable, and silent about this machine."""
    body = (await client.get("/llm/catalog/local")).json()

    rows = audio_rows(body)
    assert set(rows) == AUDIO_IDS
    kokoro = rows["kokoro-82m"]
    assert kokoro["types"] == ["audio_gen"]
    assert kokoro["runnable"] and not kokoro["recommended"]
    assert kokoro["lead"] == {"quantization": "Q8_0", "why": "default"}
    assert all(b["fit"] is None and b["can_install"] for b in kokoro["builds"])


async def test_a_build_with_no_audio_cpp_offers_no_audio_rows(
    client: AsyncClient,
) -> None:
    """No audio folder means Electron staged no audio.cpp for this host."""
    body = (await client.get("/llm/catalog/local")).json()

    assert not audio_rows(body)


async def install(
    client: AsyncClient, model: str, quantization: str, *, select: bool = False
) -> list[dict]:
    """Install one curated audio build through the one install stream."""
    body = (await client.get("/llm/catalog/local")).json()
    (build,) = [
        b
        for b in audio_rows(body)[model]["builds"]
        if b["quantization"] == quantization
    ]
    reply = await client.post(
        "/llm/install", json={"catalog_id": build["catalog_id"], "select": select}
    )
    return [json.loads(line) for line in reply.text.splitlines()]


async def test_an_audio_build_installs_into_its_folder_and_names_itself_in_the_config(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """Electron starts audio.cpp's server from `server.json` and restarts it
    when the file changes, so the install is what makes the model reachable."""
    events = await install(client, "kokoro-82m", "Q8_0")

    assert events[-1]["type"] == "complete", events[-1]
    assert (audio_dir / "kokoro-82m-q8_0.gguf").exists()
    config = json.loads((audio_dir / "server.json").read_text())
    assert config == {
        "lazy_load": True,
        "models": [
            {
                "id": "kokoro-82m-q8_0",
                "family": "kokoro_tts",
                "path": (audio_dir / "kokoro-82m-q8_0.gguf").as_posix(),
                "task": "tts",
                "mode": "offline",
            }
        ],
    }


async def test_deleting_audio_models_rewrites_the_config_and_the_last_removes_it(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The server refuses an empty model list, so with nothing left installed
    the file goes and Electron stops the server."""
    await install(client, "kokoro-82m", "Q8_0")
    await install(client, "kitten-tts-mini-0.8", "orig")

    reply = await client.delete("/llm/models/kokoro-82m-q8_0")

    assert reply.status_code == 200, reply.text
    assert not (audio_dir / "kokoro-82m-q8_0.gguf").exists()
    config = json.loads((audio_dir / "server.json").read_text())
    assert [m["id"] for m in config["models"]] == ["kitten-tts-mini-0.8-orig"]

    reply = await client.delete("/llm/models/kitten-tts-mini-0.8-orig")

    assert reply.status_code == 200, reply.text
    assert not (audio_dir / "server.json").exists()


async def test_an_installed_audio_model_can_take_the_audio_slot(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """It carries no connection, which selected_models must permit."""
    await install(client, "kokoro-82m", "Q8_0")

    chosen = await client.put(
        "/llm/selection/audio_gen",
        json={"provider": "audiocpp", "connection_id": None, "name": "kokoro-82m-q8_0"},
    )

    assert chosen.status_code == 200, chosen.text
    read = (await client.get("/llm/selection/audio_gen")).json()
    assert (read["provider"], read["name"]) == ("audiocpp", "kokoro-82m-q8_0")


@pytest.mark.parametrize(
    ("model_type", "name", "connection_id"),
    [
        pytest.param("audio_gen", "supertonic-3-f16", None, id="not installed"),
        pytest.param("text_gen", "kokoro-82m-q8_0", None, id="another type"),
        pytest.param("audio_gen", "kokoro-82m-q8_0", 1, id="with a connection"),
    ],
)
async def test_audio_cpp_takes_only_an_installed_model_for_the_audio_slot(
    client: AsyncClient,
    audio_dir,
    fake_hub,
    model_type: str,
    name: str,
    connection_id: int | None,
) -> None:
    """Electron would start the server on nothing, or a slot would name a
    runtime that cannot fill it."""
    await install(client, "kokoro-82m", "Q8_0")

    refused = await client.put(
        f"/llm/selection/{model_type}",
        json={"provider": "audiocpp", "connection_id": connection_id, "name": name},
    )

    assert refused.status_code == 422, refused.text


async def test_an_audio_row_says_what_voicing_takes_and_what_it_speaks(
    client: AsyncClient, audio_dir
) -> None:
    """The Audio section shows each model's memory while voicing, its voices
    and its languages; the server reports none of them."""
    rows = audio_rows((await client.get("/llm/catalog/local")).json())

    kokoro = rows["kokoro-82m"]["voicing"]
    assert (kokoro["peak_mb"], kokoro["voice_count"]) == (2347, 46)
    assert "en-GB" in kokoro["languages"] and len(kokoro["languages"]) == 8
    assert rows["kitten-tts-mini-0.8"]["voicing"]["languages"] == ["en"]


async def test_the_chosen_audio_model_leads_its_row_as_in_use(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The Audio section marks the model podcasts will voice with."""
    await install(client, "kokoro-82m", "Q8_0")
    await client.put(
        "/llm/selection/audio_gen",
        json={"provider": "audiocpp", "connection_id": None, "name": "kokoro-82m-q8_0"},
    )

    kokoro = audio_rows((await client.get("/llm/catalog/local")).json())["kokoro-82m"]

    assert kokoro["lead"] == {"quantization": "Q8_0", "why": "in_use"}
    assert [b["selected"] for b in kokoro["builds"]] == [True, False]


async def test_an_audio_build_installed_with_select_becomes_the_audio_selection(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """The one install stream fills the engine's own slot."""
    events = await install(client, "supertonic-3", "F16", select=True)

    assert events[-1]["type"] == "complete", events[-1]
    selection = events[-1]["selection"]
    assert (selection["model_type"], selection["provider"], selection["name"]) == (
        "audio_gen",
        "audiocpp",
        "supertonic-3-f16",
    )


async def test_deleting_the_chosen_audio_model_clears_the_audio_selection(
    client: AsyncClient, audio_dir, fake_hub
) -> None:
    """A selection must never name a model that is no longer on disk."""
    await install(client, "kokoro-82m", "Q8_0", select=True)

    reply = await client.delete("/llm/models/kokoro-82m-q8_0")

    assert reply.status_code == 200, reply.text
    assert reply.json()["selection_cleared"] is True
    assert (await client.get("/llm/selection/audio_gen")).status_code == 404


async def test_a_voicing_refusal_names_a_lighter_curated_model(
    client: AsyncClient, audio_dir, fake_hub, engine, monkeypatch
) -> None:
    """The resolver hands the adapter every other curated audio model, in the
    manifest's order, so a refusal can point at one that would fit."""
    from modules.llm.providers.audiocpp.memory import NotEnoughMemoryError
    from modules.llm.resolution import resolve_text_to_speech
    from shared.db import create_session_factory

    await install(client, "kokoro-82m", "Q8_0", select=True)
    monkeypatch.setattr(
        "modules.llm.hardware.system_memory.available_bytes", lambda: 1_800_000_000
    )

    with create_session_factory(engine)() as session:
        voice = resolve_text_to_speech(session)
    with pytest.raises(NotEnoughMemoryError) as refused:
        voice.check_memory()

    assert str(refused.value).endswith("Supertonic 3 needs about 1.6 GB.")


def kokoro_q8(body: dict) -> dict:
    """Kokoro's default build as the catalog lists it."""
    builds = audio_rows(body)["kokoro-82m"]["builds"]
    return next(b for b in builds if b["quantization"] == "Q8_0")


async def test_the_voice_the_app_ships_reads_installed_and_bundled(
    client: AsyncClient, audio_dir, bundled_voice
) -> None:
    """Kokoro comes in the installer, so it is on this computer from the first
    start, with nothing downloaded into the audio folder."""
    body = (await client.get("/llm/catalog/local")).json()

    build = kokoro_q8(body)
    assert (build["installed_as"], build["bundled"]) == ("kokoro-82m-q8_0", True)
    assert not (audio_dir / "kokoro-82m-q8_0.gguf").exists()


async def test_the_voice_the_app_ships_cannot_be_deleted(
    client: AsyncClient, audio_dir, bundled_voice
) -> None:
    """It is part of the install, as the embedding model is; a delete would
    otherwise find no file of its own and clear the podcast's voice."""
    await client.put(
        "/llm/selection/audio_gen",
        json={"provider": "audiocpp", "name": "kokoro-82m-q8_0"},
    )

    reply = await client.delete("/llm/models/kokoro-82m-q8_0")

    assert reply.status_code == 409
    assert reply.json()["detail"] == (
        "kokoro-82m-q8_0 comes with SurfSense and cannot be deleted"
    )
    assert (bundled_voice / "kokoro-82m-q8_0.gguf").exists()
    chosen = (await client.get("/llm/selection/audio_gen")).json()
    assert chosen["name"] == "kokoro-82m-q8_0"


async def test_the_config_names_the_shipped_voice_where_it_lies(
    audio_dir, bundled_voice
) -> None:
    """Read in place from the models pack, so the server starts at the first
    launch with nothing copied into the audio folder."""
    from modules.llm.catalog.local.dependencies import get_local_catalog

    get_local_catalog().audiocpp.on_startup()

    config = json.loads((audio_dir / "server.json").read_text())
    assert config["models"] == [
        {
            "id": "kokoro-82m-q8_0",
            "family": "kokoro_tts",
            "path": (bundled_voice / "kokoro-82m-q8_0.gguf").as_posix(),
            "task": "tts",
            "mode": "offline",
        }
    ]


async def test_startup_gives_podcasts_the_shipped_voice_when_none_is_chosen(
    client: AsyncClient, audio_dir, bundled_voice, engine
) -> None:
    """A fresh install, or an upgrade from the Python Kokoro, voices podcasts
    without a trip to Settings."""
    from modules.llm.default_voice import choose_default_voice
    from shared.db import create_session_factory

    with create_session_factory(engine)() as session:
        await choose_default_voice(session)

    chosen = (await client.get("/llm/selection/audio_gen")).json()
    assert (chosen["provider"], chosen["name"]) == ("audiocpp", "kokoro-82m-q8_0")


async def test_startup_leaves_a_chosen_voice_alone(
    client: AsyncClient, audio_dir, bundled_voice, fake_hub, engine
) -> None:
    """The shipped voice only fills an empty slot; it never overrides a choice."""
    from modules.llm.default_voice import choose_default_voice
    from shared.db import create_session_factory

    await install(client, "supertonic-3", "F16", select=True)

    with create_session_factory(engine)() as session:
        await choose_default_voice(session)

    chosen = (await client.get("/llm/selection/audio_gen")).json()
    assert chosen["name"] == "supertonic-3-f16"


async def test_kitten_is_told_where_the_shipped_espeak_is(
    client: AsyncClient, audio_dir, fake_hub, monkeypatch, tmp_path
) -> None:
    """audio.cpp's Kitten reads eSpeak's paths only from its session options,
    not from the environment Kokoro reads, and without them looks for a system
    eSpeak most computers do not have."""
    from shared.config import get_llm_settings

    library = tmp_path / "espeak" / "libespeak-ng.so"
    data = tmp_path / "espeak" / "espeak-ng-data"
    monkeypatch.setattr(get_llm_settings(), "audio_espeak_library", library)
    monkeypatch.setattr(get_llm_settings(), "audio_espeak_data", data)

    await install(client, "kokoro-82m", "Q8_0")
    await install(client, "kitten-tts-mini-0.8", "orig")

    entries = json.loads((audio_dir / "server.json").read_text())["models"]
    by_id = {entry["id"]: entry for entry in entries}
    assert by_id["kitten-tts-mini-0.8-orig"]["session_options"] == {
        "kitten_tts.espeak_library_path": library.as_posix(),
        "kitten_tts.espeak_data_path": data.as_posix(),
    }
    assert "session_options" not in by_id["kokoro-82m-q8_0"]
