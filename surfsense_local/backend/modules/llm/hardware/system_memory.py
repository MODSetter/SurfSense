"""Host memory actually available, from the OS rather than from ggml.

ggml's CPU device reports a live figure on native Windows and, so far, nowhere
else: under WSL2 it is virtualised, and on macOS it restates physical RAM on
both the Metal and CPU devices. That number decides PARTIAL against TOO_BIG, so
it is worth asking the OS directly.
"""

import os
import subprocess
import sys


def available_bytes() -> int:
    """Best available reading, falling back to total rather than to zero."""
    if sys.platform == "darwin":
        return _darwin()
    if sys.platform.startswith("linux"):
        return _linux()
    return _total()


def _total() -> int:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return 0


def _linux() -> int:
    try:
        with open("/proc/meminfo") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return _total()


def _darwin() -> int:
    """Free plus inactive pages: what a large allocation can actually claim."""
    try:
        output = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return _total()

    page_size = 4096
    counts: dict[str, int] = {}
    for line in output.splitlines():
        if "page size of" in line:
            page_size = int(line.split("page size of")[1].split()[0])
        elif ":" in line:
            key, _, value = line.partition(":")
            digits = value.strip().rstrip(".")
            if digits.isdigit():
                counts[key.strip()] = int(digits)

    reclaimable = counts.get("Pages free", 0) + counts.get("Pages inactive", 0)
    return reclaimable * page_size if reclaimable else _total()
