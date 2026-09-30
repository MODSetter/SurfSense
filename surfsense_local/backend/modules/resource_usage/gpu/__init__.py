"""Graphics devices as the operating system reports them, one reader per platform."""

import sys
from collections.abc import Set
from typing import Protocol

from modules.resource_usage.gpu.reading import GpuReading


class GpuReader(Protocol):
    def read(self, pids: Set[int]) -> list[GpuReading]:
        """Every card; `pids` are the app's, for a platform that reads per process."""
        ...


class NoGpuReader:
    def read(self, pids: Set[int]) -> list[GpuReading]:
        return []


def platform_gpu_reader() -> GpuReader:
    """Raises when the platform's source is there but refuses; callers fall back."""
    if sys.platform == "win32":
        from modules.resource_usage.gpu.windows.reader import WindowsGpuReader

        return WindowsGpuReader()
    if sys.platform.startswith("linux"):
        from modules.resource_usage.gpu.linux.reader import LinuxGpuReader

        return LinuxGpuReader()
    if sys.platform == "darwin":
        from modules.resource_usage.gpu.darwin.reader import DarwinGpuReader

        return DarwinGpuReader()
    return NoGpuReader()
