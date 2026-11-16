"""The staged audio.cpp server runs the speech recogniser from the
`transcription.json` the app writes, request options included.

Opt-in, like the other packaging tests, and skipped unless
SURFSENSE_TEST_AUDIO_MODELS names a folder holding a curated recogniser's
default file under its published name, checked against the manifest's sha256.
Once it does, a missing server (`pnpm build:audiocpp`, or
SURFSENSE_TEST_AUDIOCPP_DIR) fails the run.
"""

import hashlib
import io
import os
import shutil
import socket
import subprocess
import sys
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.packaging

ELECTRON = Path(__file__).resolve().parents[3] / "electron"
STAGED = Path(os.environ.get("SURFSENSE_TEST_AUDIOCPP_DIR", ELECTRON / "audiocpp"))
MODELS_DIR = os.environ.get("SURFSENSE_TEST_AUDIO_MODELS")
SERVER = STAGED / (
    "audiocpp_server.exe" if sys.platform == "win32" else "audiocpp_server"
)


def _published(model) -> str:
    return model.builds[0].files[0].path.rsplit("/", 1)[-1]


# Each curated recogniser whose default file is in the folder.
RECOGNISERS = [
    m
    for m in load_local_manifest().models
    if m.transcription
    and MODELS_DIR is not None
    and (Path(MODELS_DIR) / _published(m)).is_file()
]

if not RECOGNISERS:
    pytest.skip(
        "needs a curated recogniser's file in SURFSENSE_TEST_AUDIO_MODELS",
        allow_module_level=True,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module", params=RECOGNISERS, ids=lambda m: m.id)
def installed(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> AudioCppEngine:
    """The recogniser linked into an audio folder and recorded, as an install
    leaves it; the engine's startup writes `transcription.json` from that."""
    recogniser = request.param
    pinned = recogniser.builds[0].files[0]
    name = _published(recogniser)
    audio = tmp_path_factory.mktemp("audio")
    source = Path(MODELS_DIR) / name  # type: ignore[arg-type]
    assert _sha256(source) == pinned.sha256, f"{name} is not the pinned file"
    try:
        (audio / name).symlink_to(source)
    except OSError:  # Windows without the symlink privilege
        shutil.copyfile(source, audio / name)
    record_install(
        audio,
        InstalledBuild(
            model_id=name.removesuffix(".gguf"),
            repo=pinned.repo,
            revision=pinned.revision,
            quantization=recogniser.builds[0].quantization,
            weights=(name,),
        ),
    )
    engine = AudioCppEngine(audio, [recogniser])
    engine.on_startup()
    return engine


@pytest.fixture(scope="module")
def server(installed: AudioCppEngine, tmp_path_factory) -> Iterator[str]:
    """The server as Electron's transcription sidecar starts it."""
    assert SERVER.exists(), f"no staged audio.cpp server at {SERVER}"
    log_path = tmp_path_factory.mktemp("server") / "audiocpp.log"
    log = log_path.open("wb")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [
            str(SERVER),
            "--config",
            str(installed.folder / "transcription.json"),  # type: ignore[operator]
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--backend",
            "cpu",
            "--threads",
            "2",
            "--max-loaded-models",
            "1",
            "--idle-unload-ms",
            "300000",
            "--min-free-memory-mb",
            "1024",
            "--no-ui",
        ],
        cwd=STAGED,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{url}/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            pytest.fail("audio.cpp's server never answered /health")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=30)
        log.close()


def _silence(seconds: float, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\0\0" * int(seconds * rate))
    return buffer.getvalue()


def test_the_server_loads_the_recogniser_and_takes_its_request_options(
    installed: AudioCppEngine, server: str
) -> None:
    """A request merges the entry's `default_request_options` under its own,
    so a silent window that comes back 200 says the family took them."""
    (model,) = installed.recognisers()
    listed = httpx.get(f"{server}/v1/models").json()["data"]
    assert [m["id"] for m in listed] == [model.model_id]

    reply = httpx.post(
        f"{server}/v1/audio/transcriptions/details",
        data={"model": model.model_id},
        files={
            "file": (
                "window.wav",
                _silence(0.5, model.transcription.sample_rate),
                "audio/wav",
            )
        },
        timeout=120,
    )

    assert reply.status_code == 200, reply.text
    listed = httpx.get(f"{server}/v1/models").json()["data"]
    assert [m["loaded"] for m in listed] == [True]
