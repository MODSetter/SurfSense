"""Host memory read from the OS, the figure that decides PARTIAL against TOO_BIG.

Each reader is driven against sample output or a stand-in system call, because
only one of them can run on any given host.
"""

import ctypes
import io
import subprocess
from types import SimpleNamespace

import pytest

from modules.llm.hardware import system_memory

pytestmark = pytest.mark.unit

GIB = 1024**3

# vm_stat on an Apple Silicon Mac: 16 KiB pages, and free plus inactive is what
# a large allocation can claim.
VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               32768.
Pages active:                            400000.
Pages inactive:                           98304.
Pages speculative:                         5000.
Pages wired down:                        150000.
"""

MEMINFO = """MemTotal:       16314564 kB
MemFree:          812344 kB
MemAvailable:    6291456 kB
Buffers:          201828 kB
"""


@pytest.fixture
def total(monkeypatch: pytest.MonkeyPatch) -> int:
    """Physical RAM as sysconf states it: the fallback every reader shares."""
    monkeypatch.setattr(system_memory, "_total", lambda: 16 * GIB)
    return 16 * GIB


def meminfo(monkeypatch: pytest.MonkeyPatch, text: str | None) -> None:
    """/proc/meminfo with this content, or unreadable when None."""

    def fake_open(path: str, *args: object, **kwargs: object) -> io.StringIO:
        assert path == "/proc/meminfo"
        if text is None:
            raise PermissionError(path)
        return io.StringIO(text)

    monkeypatch.setattr(system_memory, "open", fake_open, raising=False)


def vm_stat(monkeypatch: pytest.MonkeyPatch, output: str | None) -> None:
    """vm_stat printing this, or failing when None."""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert command == ["vm_stat"]
        if output is None:
            raise FileNotFoundError("vm_stat")
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(system_memory.subprocess, "run", fake_run)


def test_linux_reads_memavailable_not_memfree(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """MemFree leaves out the page cache the kernel would give back."""
    meminfo(monkeypatch, MEMINFO)

    assert system_memory._linux() == 6291456 * 1024


def test_linux_without_memavailable_falls_back_to_total(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """Kernels before 3.14 do not report it."""
    meminfo(monkeypatch, "MemTotal:       16314564 kB\nMemFree:  812344 kB\n")

    assert system_memory._linux() == total


def test_linux_unreadable_meminfo_falls_back_to_total(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """A sandbox that hides /proc still gets a figure, not zero."""
    meminfo(monkeypatch, None)

    assert system_memory._linux() == total


def test_darwin_counts_free_and_inactive_pages_at_the_reported_size(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """16 KiB pages on Apple Silicon: assuming 4 KiB would read a quarter."""
    vm_stat(monkeypatch, VM_STAT)

    assert system_memory._darwin() == (32768 + 98304) * 16384


def test_darwin_falls_back_to_total_when_vm_stat_fails(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """A missing or hung vm_stat costs the live reading, not the badge."""
    vm_stat(monkeypatch, None)

    assert system_memory._darwin() == total


def test_darwin_falls_back_to_total_when_vm_stat_hangs(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """The 5 s timeout raises a SubprocessError, which costs only the live reading."""

    def hung(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(command, 5)

    monkeypatch.setattr(system_memory.subprocess, "run", hung)

    assert system_memory._darwin() == total


def test_darwin_with_nothing_reclaimable_reads_total_not_zero(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """Zero would badge every model Won't fit; total is the safer wrong answer."""
    vm_stat(monkeypatch, "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n")

    assert system_memory._darwin() == total


def test_an_unknown_platform_reads_total(
    monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    """No reader for it: physical RAM is the best floor there is."""
    monkeypatch.setattr(system_memory.sys, "platform", "freebsd14")

    assert system_memory.available_bytes() == total


def global_memory_status(monkeypatch: pytest.MonkeyPatch, succeeds: bool) -> None:
    """A stand-in kernel32 that answers GlobalMemoryStatusEx as Windows does."""

    def call(ref: object) -> int:
        status = ref._obj  # type: ignore[attr-defined]
        # Windows refuses the call unless the caller sized the struct.
        assert status.dwLength == ctypes.sizeof(status)
        status.ullAvailPhys = 6 * GIB
        return 1 if succeeds else 0

    stand_in = SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=call))
    monkeypatch.setattr(system_memory.ctypes, "windll", stand_in, raising=False)


def test_windows_reads_available_physical_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """There is no sysconf on Windows, so this call is all that keeps it off 0."""
    global_memory_status(monkeypatch, succeeds=True)

    assert system_memory._windows() == 6 * GIB


def test_windows_reads_zero_when_the_call_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed call's struct is not trusted, whatever it holds."""
    global_memory_status(monkeypatch, succeeds=False)

    assert system_memory._windows() == 0


def test_total_is_pages_times_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback every reader shares, from sysconf."""
    values = {"SC_PAGE_SIZE": 16384, "SC_PHYS_PAGES": 1048576}
    monkeypatch.setattr(system_memory.os, "sysconf", values.__getitem__, raising=False)

    assert system_memory._total() == 16 * GIB


def test_total_is_zero_without_sysconf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows has no sysconf; zero there, never an exception."""
    monkeypatch.delattr(system_memory.os, "sysconf", raising=False)

    assert system_memory._total() == 0
