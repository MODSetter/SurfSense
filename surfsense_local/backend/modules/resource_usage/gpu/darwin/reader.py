import subprocess
from collections.abc import Set

import psutil

from modules.resource_usage.gpu.darwin.ioreg import parse
from modules.resource_usage.gpu.reading import GpuReading

_COMMAND = ["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"]


class DarwinGpuReader:
    def read(self, pids: Set[int]) -> list[GpuReading]:
        """No per-process figure: the memory is RAM, already in each process's size."""
        listing = subprocess.run(
            _COMMAND, capture_output=True, text=True, timeout=5, check=True
        ).stdout
        ram = psutil.virtual_memory().total
        return [
            GpuReading(
                name=gpu.name,
                total_bytes=ram,
                used_bytes=gpu.in_use_bytes,
                unified_memory=True,
                busy_percent=gpu.busy_percent,
            )
            for gpu in parse(listing)
        ]
