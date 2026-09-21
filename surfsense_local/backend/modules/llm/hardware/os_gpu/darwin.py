"""Whether macOS itself can see a graphics card.

Apple Silicon always has one and Metal is part of the OS, so there is nothing to
query: a Mac that reports no Metal device has a staging problem, not a hardware
one. That is the whole value of the cross-check here.
"""

import platform


def reports_gpu() -> bool | None:
    """True on Apple Silicon, None anywhere else.

    None on Intel rather than False: the runtime we ship is arm64 only, so an
    Intel Mac is a machine we cannot make a claim about either way.
    """
    if platform.machine() == "arm64":
        return True
    return None
