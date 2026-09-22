"""What the operating system says about this machine's graphics hardware.

Asked for one reason: to tell a machine with no GPU apart from a machine whose
GPU the runtime cannot reach. Both look identical to ggml, which reports an
empty device list and exit 0 either way, so the OS is the second opinion.

Every platform answers True, False, or None for "I cannot tell". None is a real
answer and is never collapsed into False, because False is what badges a machine
CPU only, and doing that to a broken install is the failure this exists to stop.
"""

import sys


def os_reports_gpu() -> bool | None:
    """True, False, or None when this platform cannot say."""
    if sys.platform == "darwin":
        from modules.llm.hardware.os_gpu.darwin import reports_gpu

        return reports_gpu()
    if sys.platform == "win32":
        from modules.llm.hardware.os_gpu.windows import reports_gpu

        return reports_gpu()
    if sys.platform.startswith("linux"):
        from modules.llm.hardware.os_gpu.linux import reports_gpu

        return reports_gpu()
    return None
