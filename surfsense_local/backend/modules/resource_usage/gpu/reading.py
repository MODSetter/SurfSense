from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class GpuReading:
    """One graphics device at one instant.

    The per-process maps are None where the platform cannot attribute the device
    to processes, which is not the same as every process using none of it.
    """

    name: str
    total_bytes: int
    used_bytes: int
    # Apple Silicon: the memory is system RAM, so `total_bytes` is RAM.
    unified_memory: bool = False
    busy_percent: float | None = None
    process_bytes: Mapping[int, int] | None = None
    process_busy: Mapping[int, float] | None = None
