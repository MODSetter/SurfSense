import io
import logging
import time
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared.config import get_storage_settings

# Kokoro-82M as ONNX, so synthesis rides the onnxruntime the app already bundles.
# Staged like bge-small by scripts/fetch_kokoro_model.py.
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
MODEL_DIR_NAME = "kokoro"

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24_000  # Kokoro's output rate.
GAP_SECONDS = 0.35  # Silence between turns, so the two hosts do not run together.


@dataclass(frozen=True)
class Turn:
    """One spoken line: which voice says it, and what."""

    voice: str
    text: str


def kokoro_dir() -> Path:
    return get_storage_settings().models_dir / MODEL_DIR_NAME


def missing_kokoro_files() -> list[str]:
    """Voice-model files a machine still needs before a podcast can render."""
    directory = kokoro_dir()
    return [
        name for name in (MODEL_FILE, VOICES_FILE) if not (directory / name).is_file()
    ]


def synthesize(turns: list[Turn]) -> bytes:
    """Render dialogue turns to a single WAV, offline, on this CPU.

    WAV, not MP3: the browser plays it and stdlib writes it with no encoder to
    bundle. ponytail ceiling — larger files than MP3; upgrade path is a lame
    encoder once one is worth bundling.
    """
    missing = missing_kokoro_files()
    if missing:
        raise RuntimeError(
            "the Kokoro voice model is not installed "
            f"({', '.join(missing)}); run `uv run scripts/fetch_kokoro_model.py`"
        )

    import numpy as np

    logger.info("studio: kokoro loading engine")
    load_started = time.monotonic()
    kokoro = _engine()
    logger.info("studio: kokoro engine ready in %.1fs", time.monotonic() - load_started)
    gap = np.zeros(int(SAMPLE_RATE * GAP_SECONDS), dtype=np.float32)
    chunks: list[Any] = []
    for index, turn in enumerate(turns, start=1):
        turn_started = time.monotonic()
        logger.info(
            "studio: kokoro turn %s/%s voice=%s %s chars",
            index,
            len(turns),
            turn.voice,
            len(turn.text),
        )
        samples, _ = kokoro.create(turn.text, voice=turn.voice, speed=1.0, lang="en-us")
        logger.info(
            "studio: kokoro turn %s/%s done in %.1fs",
            index,
            len(turns),
            time.monotonic() - turn_started,
        )
        chunks.append(np.asarray(samples, dtype=np.float32))
        chunks.append(gap)

    audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
    logger.info("studio: kokoro stitching wav (%s turns)", len(turns))
    return _wav(audio)


@lru_cache(maxsize=1)
def _engine() -> Any:
    # Imported here, not at module load: the phonemiser and onnxruntime are only
    # paid for on the first podcast, and cached for the rest of the worker's life.
    from kokoro_onnx import Kokoro

    directory = kokoro_dir()
    return Kokoro(str(directory / MODEL_FILE), str(directory / VOICES_FILE))


def _wav(audio: Any) -> bytes:
    import numpy as np

    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(SAMPLE_RATE)
        sink.writeframes(pcm)
    return buffer.getvalue()
