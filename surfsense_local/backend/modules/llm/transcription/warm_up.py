"""A dictation's model loads while the speaker starts: half a second of silence
goes through the gate as a phrase would, and its text is thrown away."""

import asyncio
import logging

from modules.llm.providers.protocols import Transcriber
from modules.llm.transcription.audio_checks import SAMPLE_RATE, wav_of
from modules.llm.transcription.gate import TranscriptionGate

__all__ = ["warm_in_background"]

logger = logging.getLogger(__name__)

_SILENCE = wav_of(b"\0\0" * (SAMPLE_RATE // 2))
# Kept until done: the loop holds only a weak reference to a task.
_warming: set[asyncio.Task] = set()


def warm_in_background(
    gate: TranscriptionGate, transcriber: Transcriber, model: str
) -> None:
    """Call once memory has admitted the model."""
    task = asyncio.create_task(_warm(gate, transcriber, model))
    _warming.add(task)
    task.add_done_callback(_warming.discard)


async def _warm(gate: TranscriptionGate, transcriber: Transcriber, model: str) -> None:
    try:
        async with gate.dictation_turn(model):
            if not await transcriber.is_loaded(model):
                await transcriber.transcribe(model, _SILENCE, None)
    except Exception:
        # The first phrase loads it instead, and says what went wrong.
        logger.warning("transcription: could not warm the speech model", exc_info=True)
