import platform
import sys

_ARCH = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}
_OS = {"win32": "windows", "darwin": "macos", "linux": "linux"}


def this_platform() -> str | None:
    """The pin key for this machine, such as windows-x64; None where nothing is pinned."""
    system = _OS.get(sys.platform)
    arch = _ARCH.get(platform.machine().lower())
    return f"{system}-{arch}" if system and arch else None
