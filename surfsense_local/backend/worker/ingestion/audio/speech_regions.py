"""Where a recording holds speech: Silero over the decoded audio, read off disk a
minute at a time, each span padded by 200 ms and joined across gaps under
300 ms. Each frame's loudness is kept too, for cutting a run of speech that
outlasts a window."""

import logging
from array import array
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from modules.llm.transcription.voice_activity.model_file import silero_vad_file
from modules.llm.transcription.voice_activity.silero import (
    FRAME_BYTES,
    FRAME_SECONDS,
    SileroReader,
)
from modules.llm.transcription.voice_activity.speech_spans import (
    SpeechSpan,
    spans_in,
)

__all__ = ["HeardRecording", "hear_recording", "padded"]

logger = logging.getLogger(__name__)

_PAD_S = 0.2
_JOIN_UNDER_S = 0.3
_FRAMES_PER_READ = 1875  # a minute
_BYTES_PER_SECOND = 32000


@dataclass(frozen=True)
class HeardRecording:
    regions: list[SpeechSpan]
    # Each frame's loudness: the RMS of its samples.
    levels: Sequence[float]
    frame_s: float
    seconds: float


def hear_recording(audio: Path, *, between_reads: Callable[[], None]) -> HeardRecording:
    """`audio` is 16 kHz mono s16. Without Silero, or should it fail, all of it
    counts as speech, as a phrase does in the API: a recording is never lost
    for want of the detector. `between_reads` is the job's cancel check."""
    model = silero_vad_file()
    reader = SileroReader(model) if model.is_file() else None
    if reader is None:
        logger.warning("transcription: no Silero VAD at %s; all is speech", model)
    probabilities: array = array("f")
    levels: array = array("f")
    size = 0
    with audio.open("rb") as recording:
        while piece := recording.read(FRAME_BYTES * _FRAMES_PER_READ):
            size += len(piece)
            levels.extend(_loudness(piece))
            if reader is not None:
                try:
                    probabilities.extend(reader.read(piece))
                except Exception:
                    logger.warning("transcription: Silero failed", exc_info=True)
                    reader = None
            between_reads()
    seconds = size / _BYTES_PER_SECOND
    spans = [SpeechSpan(0.0, seconds)] if reader is None else spans_in(probabilities)
    return HeardRecording(padded(spans, seconds), levels, FRAME_SECONDS, seconds)


def padded(spans: Sequence[SpeechSpan], seconds: float) -> list[SpeechSpan]:
    """Each span widened by 200 ms within the recording, then joined to the
    one before when less than 300 ms apart."""
    regions: list[SpeechSpan] = []
    for span in spans:
        start = max(0.0, span.start_s - _PAD_S)
        end = min(seconds, span.end_s + _PAD_S)
        if regions and start - regions[-1].end_s < _JOIN_UNDER_S:
            regions[-1] = SpeechSpan(regions[-1].start_s, max(end, regions[-1].end_s))
        else:
            regions.append(SpeechSpan(start, end))
    return regions


def _loudness(piece: bytes) -> np.ndarray:
    samples = np.frombuffer(piece, dtype="<i2").astype(np.float32) / 32768
    frame = FRAME_BYTES // 2
    samples = np.pad(samples, (0, -len(samples) % frame)).reshape(-1, frame)
    return np.sqrt(np.mean(samples * samples, axis=1))
