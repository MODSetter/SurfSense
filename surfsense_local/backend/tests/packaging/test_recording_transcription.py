"""A recording through ingest end to end: the decode child, the real Silero, the
app's API on a real port, and the staged transcription server writing down three
sentences voiced by Kokoro-82M in English, Spanish and Portuguese, 3 s apart.

Opt-in, like the other packaging tests, and skipped unless
SURFSENSE_TEST_AUDIO_MODELS names a folder holding the curated recogniser's
default file under its published name, checked against the manifest's sha256.
Once it does, a missing server (`pnpm build:audiocpp`, or
SURFSENSE_TEST_AUDIOCPP_DIR) fails the run; Silero comes from
`scripts/fetch_silero_vad.py`.
"""

import contextlib
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from sqlalchemy import Engine

from api.main import create_app
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings.layout import segments_file
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.workspaces.models import Workspace
from shared.config import get_llm_settings, get_storage_settings
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.packaging

BACKEND = Path(__file__).resolve().parents[2]
STAGED = Path(
    os.environ.get(
        "SURFSENSE_TEST_AUDIOCPP_DIR", BACKEND.parent / "electron" / "audiocpp"
    )
)
MODELS_DIR = os.environ.get("SURFSENSE_TEST_AUDIO_MODELS")
SERVER = STAGED / (
    "audiocpp_server.exe" if sys.platform == "win32" else "audiocpp_server"
)
SPEECH = BACKEND / "tests" / "fixtures" / "audio" / "speech.ogg"

# Spanish and Portuguese, detected: Nemotron's.
(RECOGNISER,) = [
    m for m in load_local_manifest().models if m.id == "nemotron-3.5-asr-streaming-0.6b"
]
PINNED = RECOGNISER.builds[0].files[0]
NAME = PINNED.path.rsplit("/", 1)[-1]
MODEL = NAME.removesuffix(".gguf")

if MODELS_DIR is None or not (Path(MODELS_DIR) / NAME).is_file():
    pytest.skip(f"needs {NAME} in SURFSENSE_TEST_AUDIO_MODELS", allow_module_level=True)

# A word or two from each sentence, as Nemotron writes them.
HEARD = ("quarterly report", "informe trimestral", "relatório trimestral")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def audio_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The recogniser installed as a download leaves it; the engine's startup
    writes the transcription server's config from that."""
    audio = tmp_path / "audio"
    audio.mkdir()
    source = Path(MODELS_DIR) / NAME  # type: ignore[arg-type]
    assert _sha256(source) == PINNED.sha256, f"{NAME} is not the pinned file"
    try:
        (audio / NAME).symlink_to(source)
    except OSError:  # Windows without the symlink privilege
        shutil.copyfile(source, audio / NAME)
    record_install(
        audio,
        InstalledBuild(
            model_id=MODEL,
            repo=PINNED.repo,
            revision=PINNED.revision,
            quantization=RECOGNISER.builds[0].quantization,
            weights=(NAME,),
        ),
    )
    AudioCppEngine(audio, [RECOGNISER]).on_startup()
    monkeypatch.setattr(get_llm_settings(), "audio_models_dir", audio)
    get_local_catalog.cache_clear()
    yield audio
    get_local_catalog.cache_clear()


@pytest.fixture
def transcription_server(
    audio_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """The server as Electron's transcription sidecar starts it, told to the API."""
    assert SERVER.exists(), f"no staged audio.cpp server at {SERVER}"
    port = _free_port()
    threads = str(max(1, min(8, (os.cpu_count() or 2) // 2)))
    with (tmp_path / "audiocpp.log").open("wb") as log:
        process = subprocess.Popen(
            [
                str(SERVER),
                *("--config", str(audio_folder / "transcription.json")),
                *("--host", "127.0.0.1", "--port", str(port)),
                *("--backend", "cpu", "--threads", threads),
                *("--max-loaded-models", "1", "--idle-unload-ms", "300000"),
                *("--min-free-memory-mb", "1024", "--no-ui"),
            ],
            cwd=STAGED,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                with contextlib.suppress(httpx.HTTPError):
                    if httpx.get(f"{url}/health").status_code == 200:
                        break
                time.sleep(0.5)
            else:
                pytest.fail("audio.cpp's server never answered /health")
            monkeypatch.setattr(get_llm_settings(), "transcription_base_url", url)
            yield url
        finally:
            process.terminate()
            process.wait(timeout=30)


@pytest.fixture
def api(
    transcription_server: str, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """The app's API on a real port, where the worker is told it is."""
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        assert time.monotonic() < deadline, "the API did not start"
        time.sleep(0.05)
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", str(port))
    url = f"http://127.0.0.1:{port}"
    chosen = httpx.put(
        f"{url}/llm/selection/speech_to_text",
        json={"provider": "audiocpp", "name": MODEL},
        timeout=30,
    )
    assert chosen.status_code == 200, chosen.text
    yield url
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def stub_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """The transcript is what is under test, not the embedder."""

    def embed(spec: Any, texts: list[str], _purpose: Any) -> list[list[float]]:
        return [[float(len(text) % 97)] * spec.dimension for text in texts]

    monkeypatch.setattr("modules.embedding.encoder.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )


def test_a_recording_becomes_a_transcript_through_the_real_server(
    api: str, engine: Engine, real_silero_vad, stub_embedder, record_property
) -> None:
    """Two windows, cut at a pause; every sentence written down at its time."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Recordings")
        session.add(workspace)
        session.flush()
        recording = Document(
            workspace_id=workspace.id,
            title="standup.ogg",
            document_type=DocumentType.FILE,
            document_metadata={"mime_type": "audio/ogg", "suffix": ".ogg"},
        )
        session.add(recording)
        session.commit()
        folder = get_storage_settings().document_dir(workspace.id, recording.id)
        folder.mkdir(parents=True)
        shutil.copyfile(SPEECH, folder / "standup.ogg")
        document_id = recording.id

    started = time.monotonic()
    run(document_id)
    seconds = time.monotonic() - started

    with create_session_factory(engine)() as session:
        recording = session.get(Document, document_id)
        assert recording.status is DocumentStatus.READY, recording.error_message
        content = recording.content
        metadata = recording.document_metadata["transcription"]
        session.commit()
    record_property("seconds", round(seconds, 1))
    # Escaped: a Windows console cannot print every script.
    sys.stdout.write(f"\n{seconds:.1f} s\n{content!a}\n")
    paragraphs = content.split("\n\n")
    assert paragraphs[0].startswith("Transcript of standup.ogg · 0:36 · ")
    assert paragraphs[1].startswith("[00:00:00] ")
    assert paragraphs[2].startswith("[00:00:2")
    for words in HEARD:
        assert words in content.lower(), words
    assert metadata["model"] == MODEL
    assert metadata["language"] in {"en", "es", "pt"}
    segments = json.loads(segments_file(folder).read_text(encoding="utf-8"))
    assert [w["line"] for w in segments["windows"]] == [3, 5]


def test_the_api_status_reads_ready_once_the_model_is_chosen(api: str) -> None:
    """What the job asks first, before decoding anything."""
    status = httpx.get(f"{api}/llm/transcription/status", timeout=10).json()

    assert (status["ready"], status["model"]) == (True, MODEL)
