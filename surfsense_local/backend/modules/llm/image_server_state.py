"""The states the screen may report for the chosen local image model's server."""

from enum import StrEnum


class ImageServerState(StrEnum):
    NONE = "none"  # no local image model chosen for this slot
    IDLE = "idle"  # chosen, and starts when Studio needs it
    RUNNING = "running"  # sd-server is up on its weights
    MISSING = "missing"  # chosen, but a file it needs is gone, so nothing starts
