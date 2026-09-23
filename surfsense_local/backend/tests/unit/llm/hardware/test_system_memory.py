"""Host memory on Windows, which has no `os.sysconf` and used to read 0.

`kernel32` is replaced with a stand-in that fills the structure it is handed,
the way `GlobalMemoryStatusEx` does, so these run on any host.
"""

import ctypes
import sys
from types import SimpleNamespace

import pytest

from modules.llm.hardware.system_memory import available_bytes

pytestmark = pytest.mark.unit

_GIB = 1024 * 1024 * 1024


def on_windows(monkeypatch, fill) -> None:
    """Pretend to be Windows, with `fill` standing in for GlobalMemoryStatusEx."""
    monkeypatch.setattr(sys, "platform", "win32")
    kernel32 = SimpleNamespace(GlobalMemoryStatusEx=fill)
    monkeypatch.setattr(
        ctypes, "windll", SimpleNamespace(kernel32=kernel32), raising=False
    )


def reporting(avail: int, total: int):
    """A GlobalMemoryStatusEx that succeeds with these two figures."""

    def fill(pointer) -> int:
        status = pointer._obj
        assert status.dwLength == ctypes.sizeof(status), (
            "Windows rejects a wrong dwLength"
        )
        status.ullAvailPhys = avail
        status.ullTotalPhys = total
        return 1

    return fill


def test_windows_reports_available_physical_memory(monkeypatch) -> None:
    """Available, not total: this is the live budget, not the capacity one."""
    on_windows(monkeypatch, reporting(avail=6 * _GIB, total=16 * _GIB))

    assert available_bytes() == 6 * _GIB


def test_windows_falls_back_to_total_rather_than_zero(monkeypatch) -> None:
    """The module's promise on every platform: total before nothing."""
    on_windows(monkeypatch, reporting(avail=0, total=16 * _GIB))

    assert available_bytes() == 16 * _GIB


def test_windows_reads_zero_when_the_call_fails(monkeypatch) -> None:
    """A failed call leaves the structure empty, so there is nothing to report."""
    on_windows(monkeypatch, lambda pointer: 0)

    assert available_bytes() == 0


def test_windows_reads_zero_without_kernel32(monkeypatch) -> None:
    """A platform string saying win32 without the DLL must not crash the first render."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(), raising=False)

    assert available_bytes() == 0
