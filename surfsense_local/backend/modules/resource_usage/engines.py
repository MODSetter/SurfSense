"""The parts of the app a user can tell apart, and how each one's process is named."""

from enum import StrEnum


class Engine(StrEnum):
    LLAMACPP = "llamacpp"
    SDCPP = "sdcpp"
    AUDIOCPP = "audiocpp"
    BACKEND = "backend"
    INTERFACE = "interface"


# The staged binaries' names, which Electron's sidecar specs launch.
_RUNTIMES = {
    "llama-server": Engine.LLAMACPP,
    "sd-server": Engine.SDCPP,
    "audiocpp_server": Engine.AUDIOCPP,
}
# Frozen onedir binaries when packaged, the venv interpreter in development.
_BACKEND = {"api", "worker"}


def engine_of(executable: str) -> Engine:
    """Anything the shell starts that is not a sidecar is Chromium's own helpers."""
    stem = executable.lower().removesuffix(".exe")
    if stem in _RUNTIMES:
        return _RUNTIMES[stem]
    if stem in _BACKEND or stem.startswith("python"):
        return Engine.BACKEND
    return Engine.INTERFACE
