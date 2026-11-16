"""Before a request that would load the speech model, the podcast's rule: the
manifest's measured peak plus 1 GiB must be free. A model already loaded needs
no check, since the operating system's figure already leaves it out.

Speech never unloads or holds the chat model: a reload costs 10 to 26 s, and
dictated text is about to go to it. A shortfall is refused in a sentence.
"""

from collections.abc import Callable

from modules.llm.hardware import system_memory
from modules.llm.providers.audiocpp.memory import (
    NotEnoughMemoryError,
    check_memory,
    needed_bytes,
)
from modules.llm.providers.protocols import Transcriber

__all__ = ["TranscriptionNeedsMemoryError", "admit_transcription"]


class TranscriptionNeedsMemoryError(Exception):
    """The message is the sentence a person reads; the sizes let the screen
    say it in their language."""

    def __init__(self, message: str, needed_bytes: int, available_bytes: int) -> None:
        super().__init__(message)
        self.needed_bytes = needed_bytes
        self.available_bytes = available_bytes


async def admit_transcription(
    transcriber: Transcriber,
    model: str,
    peak_mb: int,
    *,
    available: Callable[[], int] | None = None,
) -> bool:
    """Whether the model is loaded already; raises when it is not and would
    not fit."""
    if await transcriber.is_loaded(model):
        return True
    # Read now, not when bound: memory moves.
    free = (available or system_memory.available_bytes)()
    try:
        check_memory("Transcribing", peak_mb, free)
    except NotEnoughMemoryError as error:
        raise TranscriptionNeedsMemoryError(
            str(error), needed_bytes(peak_mb), free
        ) from error
    return False
