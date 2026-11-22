"""The disk a decoded recording takes: 16 kHz of 16-bit mono samples, 115.2 MB
an hour, and room to spare for the checkpoints beside it."""

import math

BYTES_PER_SECOND = 16000 * 2
SPARE_BYTES = 64 * 2**20


def needed_bytes(seconds: float) -> int:
    return math.ceil(seconds * BYTES_PER_SECOND) + SPARE_BYTES
