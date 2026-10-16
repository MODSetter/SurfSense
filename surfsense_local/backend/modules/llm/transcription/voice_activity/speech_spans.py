"""Where a clip holds speech: Silero's own rule from its probabilities, at a 0.5
threshold, ending after 100 ms below 0.35, and at least 250 ms long."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from modules.llm.transcription.voice_activity.model_file import silero_vad_file
from modules.llm.transcription.voice_activity.silero import (
    FRAME_SECONDS,
    frame_probabilities,
)

__all__ = ["SpeechSpan", "spans_in", "speech_spans"]

logger = logging.getLogger(__name__)

_THRESHOLD = 0.5
_ENDS_BELOW = _THRESHOLD - 0.15
_MIN_SILENCE_S = 0.1
_MIN_SPEECH_S = 0.25


@dataclass(frozen=True)
class SpeechSpan:
    start_s: float
    end_s: float


def speech_spans(pcm: bytes) -> list[SpeechSpan] | None:
    """None when Silero cannot run, which callers take as speech: a clip is
    never dropped for want of the detector."""
    model = silero_vad_file()
    if not model.is_file():
        logger.warning(
            "transcription: no Silero VAD at %s; every clip is speech", model
        )
        return None
    try:
        return spans_in(frame_probabilities(pcm, model))
    except Exception:
        logger.warning("transcription: Silero VAD failed; clip kept", exc_info=True)
        return None


def spans_in(probabilities: Sequence[float]) -> list[SpeechSpan]:
    spans: list[SpeechSpan] = []
    start: float | None = None
    quiet_from: float | None = None
    for index, probability in enumerate(probabilities):
        at = index * FRAME_SECONDS
        if probability >= _THRESHOLD:
            quiet_from = None
            if start is None:
                start = at
            continue
        if start is None or probability >= _ENDS_BELOW:
            continue
        if quiet_from is None:
            quiet_from = at
        if at - quiet_from >= _MIN_SILENCE_S:
            if quiet_from - start >= _MIN_SPEECH_S:
                spans.append(SpeechSpan(start, quiet_from))
            start = quiet_from = None
    end = len(probabilities) * FRAME_SECONDS
    if start is not None and end - start >= _MIN_SPEECH_S:
        spans.append(SpeechSpan(start, end))
    return spans
