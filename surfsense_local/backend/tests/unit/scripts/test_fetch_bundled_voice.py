"""The voice the installer ships: staged as the catalog installs a download."""

import asyncio
import hashlib
from dataclasses import replace

import httpx
import pytest
from fetch_bundled_voice import shipped_build, stage

from modules.llm.catalog.local.installs import read_installs
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit

VOICE = b"GGUF voice"


def kokoro_q8(sha256: str):
    """Kokoro's default build, pinned to bytes a stub can serve."""
    (kokoro,) = [m for m in load_local_manifest().models if m.id == "kokoro-82m"]
    build = kokoro.as_builds()[0]
    return replace(build, files=(replace(build.files[0], sha256=sha256),))


def serving(body: bytes, asked: list[str]) -> httpx.MockTransport:
    """Hugging Face answering every URL with `body`, noting what was asked."""

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, content=body)

    return httpx.MockTransport(answer)


def test_the_pinned_build_lands_in_the_pack_with_its_install_record(tmp_path) -> None:
    """From its pinned commit, under the name and record the app reads it by."""
    build = kokoro_q8(hashlib.sha256(VOICE).hexdigest())
    asked: list[str] = []

    asyncio.run(stage(build, tmp_path, transport=serving(VOICE, asked)))

    assert asked == [
        "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/"
        f"{build.files[0].revision}/Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf"
    ]
    assert (tmp_path / "kokoro-82m-q8_0.gguf").read_bytes() == VOICE
    assert read_installs(tmp_path)["kokoro-82m-q8_0"].weights == (
        "kokoro-82m-q8_0.gguf",
    )


def test_a_file_that_is_not_the_pinned_one_is_refused(tmp_path) -> None:
    """An installer never ships bytes the manifest did not pin."""
    build = kokoro_q8(hashlib.sha256(VOICE).hexdigest())

    with pytest.raises(ValueError, match="checksum mismatch"):
        asyncio.run(stage(build, tmp_path, transport=serving(b"other", [])))

    assert not (tmp_path / "kokoro-82m-q8_0.gguf").exists()
    assert read_installs(tmp_path) == {}


def test_the_installer_ships_kokoros_default_build() -> None:
    """The manifest's first audio model, in its first build: the most voices,
    and the ids podcast briefs stored when Kokoro was the Python worker's."""
    build = shipped_build(load_local_manifest().models)

    assert build.runtime_name == "kokoro-82m-q8_0"
