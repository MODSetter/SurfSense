import io
import logging
import time
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio, Voice
from shared.config import get_storage_settings

# Kokoro-82M as ONNX, so synthesis rides the onnxruntime the app already bundles.
# Staged like bge-small by scripts/fetch_kokoro_model.py.
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
MODEL_DIR_NAME = "kokoro"

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24_000  # Kokoro's output rate.
GAP_SECONDS = 0.35  # Silence between turns, so the hosts do not run together.

# Voice ids are "<language><gender>_<name>"; the prefix picks the language and
# the espeak code the phonemiser needs for it. ponytail: Japanese and Mandarin
# voices exist in the file but espeak voices them poorly; they join when a
# proper G2P for them is bundled. The "santa" novelty voices are left out.
_LANGUAGES = {
    "a": ("en-US", "en-us"),
    "b": ("en-GB", "en-gb"),
    "e": ("es", "es"),
    "f": ("fr", "fr-fr"),
    "h": ("hi", "hi"),
    "i": ("it", "it"),
    "p": ("pt-BR", "pt-br"),
}
# fmt: off
_VOICE_IDS = [
    "af_heart", "af_bella", "af_nicole", "af_nova", "af_sarah", "af_sky", "af_alloy",
    "af_aoede", "af_jessica", "af_kore", "af_river",
    "am_adam", "am_echo", "am_eric", "am_liam", "am_michael", "am_onyx", "am_puck",
    "am_fenrir",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    "ef_dora", "em_alex",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "pf_dora", "pm_alex",
]
# fmt: on
VOICES = [
    Voice(voice_id, voice_id.split("_")[1].title(), _LANGUAGES[voice_id[0]][0])
    for voice_id in _VOICE_IDS
]


def _espeak_code(voice_id: str) -> str:
    return _LANGUAGES[voice_id[0]][1]


def kokoro_dir() -> Path:
    return get_storage_settings().models_dir / MODEL_DIR_NAME


def missing_files() -> list[str]:
    """Voice-model files a machine still needs before a podcast can render."""
    directory = kokoro_dir()
    return [
        name for name in (MODEL_FILE, VOICES_FILE) if not (directory / name).is_file()
    ]


class KokoroProvider:
    """Offline TextToSpeech on this CPU. WAV out: the browser plays it and stdlib
    writes it with no encoder to bundle. ponytail ceiling — larger than MP3; the
    upgrade is an encoder once one is worth bundling."""

    def voices(self) -> list[Voice]:
        return VOICES

    async def synthesize(self, turns: list[SpokenTurn]) -> SynthesizedAudio:
        import numpy as np

        logger.info("kokoro: loading engine")
        load_started = time.monotonic()
        kokoro = _engine()
        logger.info("kokoro: engine ready in %.1fs", time.monotonic() - load_started)
        gap = np.zeros(int(SAMPLE_RATE * GAP_SECONDS), dtype=np.float32)
        chunks: list[Any] = []
        for index, turn in enumerate(turns, start=1):
            turn_started = time.monotonic()
            logger.info(
                "kokoro: turn %s/%s voice=%s %s chars",
                index,
                len(turns),
                turn.voice,
                len(turn.text),
            )
            samples, _ = kokoro.create(
                turn.text, voice=turn.voice, speed=1.0, lang=_espeak_code(turn.voice)
            )
            logger.info(
                "kokoro: turn %s/%s done in %.1fs",
                index,
                len(turns),
                time.monotonic() - turn_started,
            )
            chunks.append(np.asarray(samples, dtype=np.float32))
            chunks.append(gap)

        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        logger.info("kokoro: stitching wav (%s turns)", len(turns))
        return SynthesizedAudio(_wav(audio), "audio/wav")


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
