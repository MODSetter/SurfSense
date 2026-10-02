"""NVIDIA cards through NVML, the library nvidia-smi reads.

The proprietary driver puts nothing about memory in sysfs, so NVML is the only
source. It ships with the driver, so a machine without it has no NVIDIA card
to read.
"""

import ctypes
from collections.abc import Set

from modules.resource_usage.gpu.reading import GpuReading

_SUCCESS = 0
_INSUFFICIENT_SIZE = 7
_NOT_AVAILABLE = 0xFFFFFFFFFFFFFFFF  # NVML_VALUE_NOT_AVAILABLE


class _Memory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _ProcessInfo(ctypes.Structure):
    """nvmlProcessInfo_t as the _v2 and _v3 listings fill it."""

    _fields_ = [
        ("pid", ctypes.c_uint),
        ("usedGpuMemory", ctypes.c_ulonglong),
        ("gpuInstanceId", ctypes.c_uint),
        ("computeInstanceId", ctypes.c_uint),
    ]


class NvmlReader:
    def __init__(self) -> None:
        self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
        if self._nvml.nvmlInit_v2() != _SUCCESS:
            raise OSError("NVML did not initialise")
        count = ctypes.c_uint()
        if self._nvml.nvmlDeviceGetCount_v2(ctypes.byref(count)) != _SUCCESS:
            raise OSError("NVML listed no devices")
        self._devices: list[tuple[ctypes.c_void_p, str]] = []
        for index in range(count.value):
            handle = ctypes.c_void_p()
            if self._nvml.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(handle)):
                continue
            name = ctypes.create_string_buffer(96)
            self._nvml.nvmlDeviceGetName(handle, name, len(name))
            self._devices.append(
                (handle, name.value.decode(errors="replace") or "NVIDIA GPU")
            )
        # Vulkan work lists as graphics, CUDA as compute; a process can be both.
        self._listings = [
            listing
            for kind in ("Compute", "Graphics")
            if (
                listing := _function(self._nvml, f"nvmlDeviceGet{kind}RunningProcesses")
            )
        ]

    @property
    def found(self) -> bool:
        return bool(self._devices)

    def read(self, pids: Set[int]) -> list[GpuReading]:
        readings = []
        for handle, name in self._devices:
            memory = _Memory()
            if (
                self._nvml.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(memory))
                != _SUCCESS
            ):
                continue
            utilization = _Utilization()
            busy = (
                float(utilization.gpu)
                if self._nvml.nvmlDeviceGetUtilizationRates(
                    handle, ctypes.byref(utilization)
                )
                == _SUCCESS
                else None
            )
            readings.append(
                GpuReading(
                    name=name,
                    total_bytes=memory.total,
                    used_bytes=memory.used,
                    busy_percent=busy,
                    process_bytes=self._process_bytes(handle)
                    if self._listings
                    else None,
                )
            )
        return readings

    def _process_bytes(self, handle: ctypes.c_void_p) -> dict[int, int]:
        shares: dict[int, int] = {}
        for listing in self._listings:
            for info in _processes(listing, handle):
                if info.usedGpuMemory != _NOT_AVAILABLE:
                    # Listed as both compute and graphics: the same memory twice.
                    shares[info.pid] = max(shares.get(info.pid, 0), info.usedGpuMemory)
        return shares


def _function(nvml: ctypes.CDLL, stem: str):
    """The newest listing this driver exports with the four-field process record."""
    for suffix in ("_v3", "_v2"):
        try:
            return getattr(nvml, stem + suffix)
        except AttributeError:
            continue
    return None


def _processes(listing, handle: ctypes.c_void_p) -> list[_ProcessInfo]:
    capacity = 64
    for _ in range(3):
        count = ctypes.c_uint(capacity)
        infos = (_ProcessInfo * capacity)()
        status = listing(handle, ctypes.byref(count), infos)
        if status == _SUCCESS:
            return list(infos[: count.value])
        if status != _INSUFFICIENT_SIZE:
            return []
        capacity = count.value + 16
    return []
