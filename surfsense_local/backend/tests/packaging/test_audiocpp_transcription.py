"""Kokoro voices known sentences in six languages, and the staged transcription
server writes them down through the app's own client, language tags, cleanup
and all: the error and the language heard stay within bounds, and the server's
peak memory is recorded.

Opt-in, like the other packaging tests, and skipped unless
SURFSENSE_TEST_AUDIO_MODELS names a folder holding Kokoro's and the curated
recogniser's default files under their published names, each checked against
the manifest's sha256. Once it does, a missing server (`pnpm build:audiocpp`, or
SURFSENSE_TEST_AUDIOCPP_DIR) fails the run. One staged binary serves both, as
in the app; Silero's check runs when `scripts/fetch_silero_vad.py` staged it.
"""

import asyncio
import contextlib
import hashlib
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import wave
from collections.abc import Iterator
from pathlib import Path

import httpx
import numpy as np
import psutil
import pytest
from scipy.signal import resample_poly

from modules.llm.catalog.local.engines.audiocpp.audio_folder.espeak import Espeak
from modules.llm.catalog.local.engines.audiocpp.engine import AudioCppEngine
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.providers.audiocpp.speech import AudioCppSpeech, VoicedModel
from modules.llm.providers.audiocpp.transcription import AudioCppTranscriber
from modules.llm.providers.protocols import SpokenTurn
from modules.llm.transcription.audio_checks import checked_audio, wav_of
from modules.llm.transcription.recognition import recognise
from modules.llm.transcription.selected_model import SpeechModel
from modules.llm.transcription.voice_activity.speech_spans import speech_spans

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

MODELS = {m.id: m for m in load_local_manifest().models}
# Its language tags and six languages are Nemotron's.
RECOGNISER = MODELS["nemotron-3.5-asr-streaming-0.6b"]
KOKORO = MODELS["kokoro-82m"]


def _published(model) -> str:
    return model.builds[0].files[0].path.rsplit("/", 1)[-1]


if MODELS_DIR is None or not all(
    (Path(MODELS_DIR) / _published(m)).is_file() for m in (RECOGNISER, KOKORO)
):
    pytest.skip(
        "needs Kokoro's and the recogniser's files in SURFSENSE_TEST_AUDIO_MODELS",
        allow_module_level=True,
    )

# Each language's sentence and the Kokoro voice that says it; both models' own
# measurement used these. Nemotron writes "doce" as "12", hence the bound.
SENTENCES = {
    "en": (
        "af_heart",
        "The quarterly report shows that revenue grew by twelve percent, mostly "
        "because customers renewed their annual plans earlier than expected.",
    ),
    "es": (
        "ef_dora",
        "El informe trimestral muestra que los ingresos crecieron un doce por "
        "ciento, sobre todo porque los clientes renovaron sus planes anuales "
        "antes de lo previsto.",
    ),
    "fr": (
        "ff_siwis",
        "Le rapport trimestriel montre que le chiffre d'affaires a augmenté de "
        "douze pour cent, surtout parce que les clients ont renouvelé leurs "
        "abonnements plus tôt que prévu.",
    ),
    "hi": (
        "hf_alpha",
        "तिमाही रिपोर्ट से पता चलता है कि राजस्व में बारह प्रतिशत की वृद्धि हुई, "
        "मुख्य रूप से क्योंकि ग्राहकों ने अपनी वार्षिक योजनाओं को उम्मीद से पहले "
        "नवीनीकृत किया।",
    ),
    "pt": (
        "pf_dora",
        "O relatório trimestral mostra que a receita cresceu doze por cento, "
        "principalmente porque os clientes renovaram seus planos anuais antes "
        "do esperado.",
    ),
    "zh": (
        "zf_xiaobei",
        "季度报告显示，收入增长了百分之十二，主要是因为客户比预期更早地续订了他们的年度计划。",  # noqa: RUF001
    ),
}
# Word error, or character error for Chinese, in percent.
MAX_ERROR = 20.0
# Written in a script no other listed language uses, so named even untagged.
UNSHARED_SCRIPT = {"hi", "zh"}
# The sidecar's --threads: half the logical cores, at most 8.
THREADS = str(max(1, min(8, (os.cpu_count() or 2) // 2)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> AudioCppEngine:
    """Both files linked into an audio folder and recorded, as installs leave
    them; the engine's startup writes both servers' configs from that."""
    audio = tmp_path_factory.mktemp("audio")
    for model in (KOKORO, RECOGNISER):
        pinned = model.builds[0].files[0]
        name = _published(model)
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
    espeak = STAGED / "espeak"
    engine = AudioCppEngine(
        audio,
        [KOKORO, RECOGNISER],
        espeak=Espeak(
            espeak / ESPEAK.get(sys.platform, ESPEAK["linux"]),
            espeak / "espeak-ng-data",
        ),
    )
    engine.on_startup()
    return engine


@contextlib.contextmanager
def _running(
    config: Path, log_path: Path, env: dict[str, str]
) -> Iterator[tuple[str, psutil.Process]]:
    """The staged server with the sidecars' flags."""
    assert SERVER.exists(), f"no staged audio.cpp server at {SERVER}"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [
                str(SERVER),
                *("--config", str(config), "--host", "127.0.0.1", "--port", str(port)),
                *("--backend", "cpu", "--threads", THREADS),
                *("--max-loaded-models", "1", "--idle-unload-ms", "300000"),
                *("--min-free-memory-mb", "1024", "--no-ui"),
            ],
            cwd=STAGED,
            env={**os.environ, **env},
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
                pytest.fail(f"audio.cpp's server never answered /health: {log_path}")
            yield url, psutil.Process(process.pid)
        finally:
            process.terminate()
            process.wait(timeout=30)


@pytest.fixture(scope="module")
def voiced(installed: AudioCppEngine, tmp_path_factory) -> dict[str, bytes]:
    """Each sentence as 16 kHz mono PCM, voiced by the podcast's own server."""
    espeak = STAGED / "espeak"
    env = {
        "AUDIOCPP_ESPEAK_LIBRARY": str(
            espeak / ESPEAK.get(sys.platform, ESPEAK["linux"])
        ),
        "AUDIOCPP_ESPEAK_DATA": str(espeak / "espeak-ng-data"),
    }
    folder = installed.folder
    assert folder is not None
    log = tmp_path_factory.mktemp("voices") / "audiocpp.log"
    with _running(folder / "server.json", log, env) as (url, _):
        model = installed.installed_model(_published(KOKORO).removesuffix(".gguf"))
        assert model is not None
        speech = AudioCppSpeech(
            VoicedModel(model.model_id, model.audio),
            base_url=url,
            give_up_text_runtime=contextlib.nullcontext,
        )
        clips = {}
        for language, (voice, sentence) in SENTENCES.items():
            spoken = asyncio.run(speech.synthesize([SpokenTurn(voice, sentence)], ""))
            clips[language] = _as_16k(spoken.content)
    return clips


@pytest.fixture(scope="module")
def transcription(
    installed: AudioCppEngine, tmp_path_factory
) -> Iterator[tuple[str, psutil.Process]]:
    """The transcription server as Electron's second sidecar starts it."""
    folder = installed.folder
    assert folder is not None
    log = tmp_path_factory.mktemp("transcription") / "audiocpp.log"
    with _running(folder / "transcription.json", log, {}) as server:
        yield server


def _as_16k(wav: bytes) -> bytes:
    with wave.open(io.BytesIO(wav)) as clip:
        rate = clip.getframerate()
        samples = np.frombuffer(clip.readframes(clip.getnframes()), dtype="<i2")
    resampled = resample_poly(samples.astype(np.float32), 16000, rate)
    return np.clip(resampled, -32768, 32767).astype("<i2").tobytes()


class PeakMemory:
    """The server's resident memory, sampled every 25 ms."""

    def __init__(self, process: psutil.Process) -> None:
        self._process = process
        self.peak = process.memory_info().rss
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        while not self._stop.wait(0.025):
            with contextlib.suppress(psutil.Error):
                self.peak = max(self.peak, self._process.memory_info().rss)

    def stop(self) -> int:
        self._stop.set()
        self._thread.join()
        return self.peak


def _error(reference: str, heard: str, language: str) -> float:
    def units(text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text).lower()
        if language == "zh":
            return [c for c in text if c.isalnum()]
        return re.sub(r"[^\w\s']", " ", text).split()

    expected, got = units(reference), units(heard)
    previous = list(range(len(got) + 1))
    for i, unit in enumerate(expected, 1):
        current = [i]
        for j, other in enumerate(got, 1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (unit != other),
                )
            )
        previous = current
    return 100 * previous[-1] / max(1, len(expected))


def test_the_server_writes_down_each_language_through_the_app(
    installed: AudioCppEngine,
    voiced: dict[str, bytes],
    transcription: tuple[str, psutil.Process],
    record_property,
) -> None:
    """Auto-detected, as a new choice is: the language comes from the last tag,
    or with none from a script only one language writes."""
    url, process = transcription
    (recogniser,) = installed.recognisers()
    model = SpeechModel(recogniser.model_id, recogniser.transcription, "auto")
    transcriber = AudioCppTranscriber(url)
    memory = PeakMemory(process)
    results = {}
    for language, pcm in voiced.items():
        clip = checked_audio(wav_of(pcm))
        results[language] = asyncio.run(recognise(transcriber, model, clip))
    peak_mib = memory.stop() / 2**20

    record_property("peak_mib", round(peak_mib))
    record_property("languages", {k: v.language for k, v in results.items()})
    sys.stdout.write(f"\ntranscription server peak: {peak_mib:.0f} MiB\n")
    for language, recognised in results.items():
        error = _error(SENTENCES[language][1], recognised.text, language)
        # Escaped: a Windows console cannot print Devanagari.
        sys.stdout.write(
            f"{language}: {error:.1f}% {recognised.language} {recognised.text!a}\n"
        )
        assert error <= MAX_ERROR, (language, recognised.text)
        # Untagged Latin text names no language; an unshared script does.
        named = (language,) if language in UNSHARED_SCRIPT else (language, None)
        assert recognised.language in named, (language, recognised)


def test_the_model_is_given_back_by_its_id(
    installed: AudioCppEngine, transcription: tuple[str, psutil.Process]
) -> None:
    """As a hold or a recording's last window does, leaving voices alone."""
    url, _ = transcription
    (recogniser,) = installed.recognisers()
    transcriber = AudioCppTranscriber(url)
    asyncio.run(
        transcriber.transcribe(recogniser.model_id, wav_of(b"\0\0" * 8000), None)
    )

    assert asyncio.run(transcriber.is_loaded(recogniser.model_id)) is True
    asyncio.run(transcriber.unload(recogniser.model_id))
    assert asyncio.run(transcriber.is_loaded(recogniser.model_id)) is False


def test_silero_hears_speech_in_every_sentence(
    voiced: dict[str, bytes], real_silero_vad
) -> None:
    """Real speech in six languages passes the gate that drops a cough."""
    for language, pcm in voiced.items():
        spans = speech_spans(pcm)
        assert spans, language
        assert sum(s.end_s - s.start_s for s in spans) > 3.0, (language, spans)
