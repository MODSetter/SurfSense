"""Before a request that would load the speech model: its measured peak and a
gibibyte more must be free, unless it is loaded already."""

import pytest

from modules.llm.transcription.memory_admission import (
    TranscriptionNeedsMemoryError,
    admit_transcription,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

PEAK_MB = 1776
NEEDED = PEAK_MB * 2**20 + 2**30


class Server:
    def __init__(self, loaded: bool) -> None:
        self.loaded = loaded

    async def is_loaded(self, model: str) -> bool:
        return self.loaded


async def test_a_loaded_model_needs_no_check() -> None:
    """The operating system's figure already leaves its memory out."""
    loaded = await admit_transcription(Server(True), "m", PEAK_MB, available=lambda: 0)

    assert loaded is True


async def test_a_model_that_fits_may_load() -> None:
    """Exactly the peak and the headroom is enough."""
    loaded = await admit_transcription(
        Server(False), "m", PEAK_MB, available=lambda: NEEDED
    )

    assert loaded is False


async def test_a_model_that_does_not_fit_is_refused_with_both_sizes() -> None:
    """So the screen can say it in the user's language."""
    with pytest.raises(TranscriptionNeedsMemoryError) as refused:
        await admit_transcription(
            Server(False), "m", PEAK_MB, available=lambda: 1_800_000_000
        )

    assert (refused.value.needed_bytes, refused.value.available_bytes) == (
        NEEDED,
        1_800_000_000,
    )
    assert str(refused.value) == (
        "Transcribing needs about 2.9 GB free; this computer has 1.8 GB."
    )
