"""What ggml reports about one device.

The type enum is ggml's, read from `ggml-backend.h`. It has grown twice, so an
integer we do not recognise is treated as "not a GPU" rather than as an error:
this runs on the first render, and every Mac already lists a device type that a
three-member enum would reject.
"""

from dataclasses import dataclass
from enum import IntEnum


class DeviceType(IntEnum):
    """GGML_BACKEND_DEVICE_TYPE_*, in declaration order."""

    CPU = 0
    GPU = 1
    IGPU = 2  # integrated, carving from host memory
    ACCEL = 3  # BLAS, AMX. Accelerate appears on every Mac.
    META = 4  # wraps several devices for tensor parallelism
    UNKNOWN = -1

    @classmethod
    def parse(cls, raw: int) -> "DeviceType":
        try:
            return cls(raw)
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class Device:
    name: str
    description: str
    type: DeviceType
    total_bytes: int
    free_bytes: int

    @property
    def reports_live_memory(self) -> bool:
        """False when `free` merely restates `total`.

        Measured: native Windows reports real free memory, but WSL2 virtualises
        it and macOS restates the total on both the Metal and CPU devices. So a
        live figure is the exception, and the RAM half of a budget has to come
        from the OS instead.
        """
        return self.total_bytes > 0 and self.free_bytes < self.total_bytes
