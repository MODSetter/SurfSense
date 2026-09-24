"""Whether this computer has the memory a model takes while voicing.

audio.cpp's own guard compares free memory with the bytes it reads from the
file, 190 MB for Kokoro, not the 1.4 GB it takes while voicing, so the app
checks the peak its entry measured, plus headroom for everything else.
"""

HEADROOM_BYTES = 2**30


class NotEnoughMemoryError(Exception):
    """Voicing would not fit; the message is the sentence a person reads."""


def check_voicing_memory(peak_mb: int, available_bytes: int) -> None:
    needed = peak_mb * 2**20 + HEADROOM_BYTES
    if available_bytes < needed:
        raise NotEnoughMemoryError(
            f"Voicing needs about {needed / 1e9:.1f} GB free; "
            f"this computer has {available_bytes / 1e9:.1f} GB."
        )
