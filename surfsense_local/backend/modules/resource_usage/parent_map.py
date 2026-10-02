"""Every process's parent, from one snapshot of the process table."""

import psutil


def parent_map() -> dict[int, int]:
    """psutil's private map is what its own `children()` is built on. Measured on
    Windows: 26 ms, where `process_iter(["ppid"])` took 13 s cold and 290 ms warm,
    one handle per process on the machine."""
    snapshot = getattr(psutil, "_ppid_map", None)
    if snapshot is not None:
        return snapshot()
    return {p.pid: p.info["ppid"] for p in psutil.process_iter(["ppid"])}
