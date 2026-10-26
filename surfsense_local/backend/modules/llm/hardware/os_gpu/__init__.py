"""What the operating system says about this machine's graphics hardware.

Asked to tell a machine with no GPU apart from a machine whose GPU the runtime
cannot reach. Both look identical to ggml, which reports an empty device list
and exit 0 either way, so the OS is the second opinion. The usage summary also
asks it whose card that unreachable GPU is, since ggml names nothing.

Every platform answers True, False, or None for "I cannot tell". None is a real
answer and is never collapsed into False, because False is what badges a machine
CPU only, and doing that to a broken install is the failure this exists to stop.
"""

import sys
from types import ModuleType


def os_reports_gpu() -> bool | None:
    """True, False, or None when this platform cannot say."""
    reader = _platform_reader()
    return None if reader is None else reader.reports_gpu()


def os_adapter_names() -> list[str] | None:
    """The real adapters this OS lists, from the same source `os_reports_gpu` reads.

    None when this platform cannot say. Not cached: on Windows each call starts
    PowerShell, so a caller that asks often keeps the answer.
    """
    reader = _platform_reader()
    return None if reader is None else reader.adapter_names()


def _platform_reader() -> ModuleType | None:
    if sys.platform == "darwin":
        from modules.llm.hardware.os_gpu import darwin

        return darwin
    if sys.platform == "win32":
        from modules.llm.hardware.os_gpu import windows

        return windows
    if sys.platform.startswith("linux"):
        from modules.llm.hardware.os_gpu import linux

        return linux
    return None
