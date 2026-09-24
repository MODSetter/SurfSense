"""Whether this computer has the memory a model takes while voicing.

audio.cpp's own guard compares free memory with the bytes it reads from the
file, 190 MB for Kokoro, not the 1.4 GB it takes while voicing, so the app
checks the peak its entry measured, plus headroom for everything else.
"""

from collections.abc import Sequence
from dataclasses import dataclass

HEADROOM_BYTES = 2**30


class NotEnoughMemoryError(Exception):
    """Voicing would not fit; the message is the sentence a person reads."""


@dataclass(frozen=True)
class OtherModel:
    """Another curated audio model, by its name and measured peak."""

    name: str
    peak_mb: int


def _needed(peak_mb: int) -> int:
    return peak_mb * 2**20 + HEADROOM_BYTES


def check_voicing_memory(
    peak_mb: int, available_bytes: int, others: Sequence[OtherModel] = ()
) -> None:
    """`others` in the manifest's order: the first that fits is named, since a
    lighter model voices at full quality where a smaller chunk would not."""
    needed = _needed(peak_mb)
    if available_bytes >= needed:
        return
    sentence = (
        f"Voicing needs about {needed / 1e9:.1f} GB free; "
        f"this computer has {available_bytes / 1e9:.1f} GB."
    )
    fits = next((o for o in others if _needed(o.peak_mb) <= available_bytes), None)
    if fits is not None:
        sentence += f" {fits.name} needs about {_needed(fits.peak_mb) / 1e9:.1f} GB."
    raise NotEnoughMemoryError(sentence)
