"""The machine in the report's buckets: memory, and the GPU the model runtime prices against."""

from collections.abc import Callable, Sequence

from modules.llm.hardware import DeviceType, GpuStatus, SystemInventory, select_device
from modules.usage_statistics.buckets import ram_bucket, vram_bucket
from modules.usage_statistics.gpu_vendor import gpu_vendor, vendor_named
from modules.usage_statistics.schemas import HardwareRead

UNKNOWN = "unknown"

OsAdapterNames = Callable[[], Sequence[str] | None]

_RUNTIME = {
    GpuStatus.PRESENT: "reachable",
    GpuStatus.BROKEN_INSTALL: "unreachable",
    GpuStatus.ABSENT: "none",
    GpuStatus.UNKNOWN: UNKNOWN,
}


def hardware_buckets(
    inventory: SystemInventory | None,
    ram_total_bytes: int | None,
    os_adapter_names: OsAdapterNames,
) -> HardwareRead | None:
    """None when memory cannot be read: the contract has no unknown for it.

    The OS is asked for its adapters only about a card the runtime cannot reach.
    """
    if not ram_total_bytes:
        return None
    gpu, vram = _gpu(inventory, os_adapter_names)
    return HardwareRead(
        ram_gb=ram_bucket(ram_total_bytes),
        gpu=gpu,
        vram_gb=vram,
        gpu_runtime=UNKNOWN if inventory is None else _RUNTIME[inventory.gpu_status],
    )


def _gpu(
    inventory: SystemInventory | None, os_adapter_names: OsAdapterNames
) -> tuple[str, str]:
    if inventory is None:
        return UNKNOWN, UNKNOWN
    if inventory.gpu_status is GpuStatus.ABSENT:
        return "none", "0"
    if inventory.gpu_status is GpuStatus.BROKEN_INSTALL:
        # ggml lists no device to name or size; the OS can still say whose card.
        return vendor_named(*(os_adapter_names() or ())) or UNKNOWN, UNKNOWN
    if inventory.gpu_status is not GpuStatus.PRESENT:
        return UNKNOWN, UNKNOWN
    # The discrete card the catalog prices against, else the integrated one.
    device = select_device(inventory.devices) or next(
        d for d in inventory.devices if d.type in (DeviceType.GPU, DeviceType.IGPU)
    )
    vram = vram_bucket(device.total_bytes) if device.total_bytes > 0 else UNKNOWN
    return gpu_vendor(device) or UNKNOWN, vram
