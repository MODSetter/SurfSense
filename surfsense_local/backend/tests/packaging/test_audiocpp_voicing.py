"""The staged audio.cpp server voices every curated model through the app's
adapter, from the config the app writes, and gives the model back after.

Opt-in, like the other packaging tests, and skipped unless
SURFSENSE_TEST_AUDIO_MODELS names a folder holding each curated model's default
file under its published name, each checked against the manifest's sha256. Once
it does, a missing server (`pnpm build:audiocpp`, or SURFSENSE_TEST_AUDIOCPP_DIR)
fails the run: CI sets the folder, and a skip there would pass unseen.
"""

import asyncio
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

from modules.llm.catalog.local.engines.audiocpp.audio_folder.espeak import Espeak
from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.providers.audiocpp.speech import AudioCppSpeech, VoicedModel
from modules.llm.providers.protocols import SpokenTurn

pytestmark = pytest.mark.packaging

ELECTRON = Path(__file__).resolve().parents[3] / "electron"
STAGED = Path(os.environ.get("SURFSENSE_TEST_AUDIOCPP_DIR", ELECTRON / "audiocpp"))
MODELS_DIR = os.environ.get("SURFSENSE_TEST_AUDIO_MODELS")
SERVER = STAGED / (
    "audiocpp_server.exe" if sys.platform == "win32" else "audiocpp_server"
)
ESPEAK = {
    "linux": "libespeak-ng.so",
    "darwin": "libespeak-ng.dylib",
    "win32": "espeak-ng.dll",
}

# Two voices and a language each model speaks; Supertonic in French, so the
# language reaches the server.
CASES = {
    "kokoro-82m": ("en-US", ["af_heart", "am_adam"]),
    "supertonic-3": ("fr", ["M1", "F1"]),
    "kitten-tts-mini-0.8": ("en", ["Bella", "Leo"]),
}
LINES = {
    "en-US": ["Welcome back to the show.", "Thanks for having me."],
    "en": ["Welcome back to the show.", "Thanks for having me."],
    "fr": ["Bonjour et bienvenue.", "Merci de m'accueillir."],
}

if MODELS_DIR is None:
    pytest.skip("needs SURFSENSE_TEST_AUDIO_MODELS", allow_module_level=True)

CURATED = {m.id: m for m in load_local_manifest().models if m.id in CASES}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> AudioCppEngine:
    """Each default build linked into an audio folder and recorded, as an
    install leaves it; the engine's startup writes `server.json` from that."""
    audio = tmp_path_factory.mktemp("audio")
    for model in CURATED.values():
        pinned = model.builds[0].files[0]
        name = pinned.path.rsplit("/", 1)[-1]
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
                quantization=model.builds[0].quantization,
                weights=(name,),
            ),
        )
    # Electron hands the API the eSpeak it staged, as it hands the server.
    espeak = STAGED / "espeak"
    engine = AudioCppEngine(
        audio,
        list(CURATED.values()),
        espeak=Espeak(
            espeak / ESPEAK.get(sys.platform, ESPEAK["linux"]),
            espeak / "espeak-ng-data",
        ),
    )
    engine.on_startup()
    return engine


@pytest.fixture(scope="module")
def server_log(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Where the server writes; a test that fails shows its tail."""
    return tmp_path_factory.mktemp("server") / "audiocpp.log"


@pytest.fixture(scope="module")
def server(installed: AudioCppEngine, server_log: Path) -> Iterator[str]:
    """The server as Electron's sidecar starts it: same flags, same eSpeak."""
    assert SERVER.exists(), f"no staged audio.cpp server at {SERVER}"
    log = server_log.open("wb")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    espeak = STAGED / "espeak"
    process = subprocess.Popen(
        [
            str(SERVER),
            "--config",
            str(installed.folder / "server.json"),  # type: ignore[operator]
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
        env={
            **os.environ,
            "AUDIOCPP_ESPEAK_LIBRARY": str(
                espeak / ESPEAK.get(sys.platform, ESPEAK["linux"])
            ),
            "AUDIOCPP_ESPEAK_DATA": str(espeak / "espeak-ng-data"),
        },
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


@pytest.mark.parametrize("model_id", list(CASES))
def test_a_curated_model_voices_through_the_app_and_is_given_back(
    installed: AudioCppEngine, server: str, server_log: Path, model_id: str
) -> None:
    """Two turns at the manifest's sample rate, then nothing left loaded."""
    language, voices = CASES[model_id]
    audio = CURATED[model_id].audio
    assert audio is not None
    name = CURATED[model_id].builds[0].files[0].path.rsplit("/", 1)[-1]
    model = installed.installed_model(name.removesuffix(".gguf"))
    assert model is not None
    speech = AudioCppSpeech(VoicedModel(model.model_id, model.audio), base_url=server)
    turns = [
        SpokenTurn(v, line) for v, line in zip(voices, LINES[language], strict=True)
    ]

    try:
        voiced = asyncio.run(speech.synthesize(turns, language))
    except Exception:
        tail = server_log.read_text(errors="replace").splitlines()[-60:]
        sys.stderr.write("\n".join(["audiocpp_server's log, last lines:", *tail]))
        raise

    with wave.open(io.BytesIO(voiced.content)) as joined:
        assert joined.getframerate() == audio.sample_rate
        assert joined.getnframes() / joined.getframerate() > 1.0
    listed = httpx.get(f"{server}/v1/models").json()["data"]
    assert not [m["id"] for m in listed if m["loaded"]]
