"""The text a recogniser wrote, made fit to read: the same for a dictated phrase
and a recording's window, and fail-open, as Handy's is: any error keeps the
text as it came.

Runaway repetition is how autoregressive decoders fail; Nemotron's transducer
rarely does, and the checks cost nothing when they do not fire.
"""

import logging
import re
import zlib

__all__ = ["cleaned"]

logger = logging.getLogger(__name__)

# Written without spaces between words, so a run is counted in characters.
_UNSPACED = frozenset({"zh", "ja", "yue", "th"})
# There a number or a Latin word is one unit, so 100000 keeps its zeros.
_UNSPACED_UNIT = re.compile(r"[\dA-Za-z]+|.", re.DOTALL)
_LONGEST_RUN = 4
_REPEATS = 4
# Faster than anyone speaks, in characters a second of audio.
_MAX_CHARS_PER_SECOND = 40
# Whisper's own threshold for a looping decode; shorter text says nothing.
_MAX_COMPRESSION_RATIO = 2.4
_RATIO_MIN_CHARS = 50


def cleaned(text: str, language: str | None, seconds: float) -> str:
    try:
        return _cleaned(text, language, seconds)
    except Exception:
        logger.warning("transcription: cleanup failed; text kept", exc_info=True)
        return text


def _cleaned(text: str, language: str | None, seconds: float) -> str:
    text = text.strip()
    if language in _UNSPACED:
        text = "".join(_collapsed(_UNSPACED_UNIT.findall(text)))
    else:
        words = text.split()
        collapsed = _collapsed(words)
        if len(collapsed) < len(words):
            text = " ".join(collapsed)
    if seconds > 0 and len(text) / seconds > _MAX_CHARS_PER_SECOND:
        logger.info("transcription: dropped %s chars for %.1f s", len(text), seconds)
        return ""
    if (
        len(text) >= _RATIO_MIN_CHARS
        and _compression_ratio(text) > _MAX_COMPRESSION_RATIO
    ):
        logger.info("transcription: dropped %s chars that loop", len(text))
        return ""
    return text


def _collapsed[T](items: list[T]) -> list[T]:
    """Any run of one to four items said four or more times in a row, once."""
    kept: list[T] = []
    at = 0
    while at < len(items):
        for size in range(1, _LONGEST_RUN + 1):
            run = items[at : at + size]
            times = 1
            while items[at + times * size : at + (times + 1) * size] == run:
                times += 1
            if len(run) == size and times >= _REPEATS:
                kept.extend(run)
                at += times * size
                break
        else:
            kept.append(items[at])
            at += 1
    return kept


def _compression_ratio(text: str) -> float:
    encoded = text.encode()
    return len(encoded) / len(zlib.compress(encoded))
