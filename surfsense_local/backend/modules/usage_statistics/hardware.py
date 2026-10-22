"""The machine in the report's buckets: memory, and the GPU the model runtime prices against."""

from modules.llm.hardware import DeviceType, GpuStatus, SystemInventory, select_device
from modules.usage_statistics.buckets import ram_bucket, vram_bucket
from modules.usage_statistics.gpu_vendor import gpu_vendor
from modules.usage_statistics.schemas import HardwareRead

UNKNOWN = "unknown"


def hardware_buckets(
    inventory: SystemInventory | None, ram_total_bytes: int | None
) -> HardwareRead | None:
    """None when memory cannot be read: the contract has no unknown for it."""
    if not ram_total_bytes:
        return None
    gpu, vram = _gpu(inventory)
    return HardwareRead(ram_gb=ram_bucket(ram_total_bytes), gpu=gpu, vram_gb=vram)


def _gpu(inventory: SystemInventory | None) -> tuple[str, str]:
    if inventory is None:
        return UNKNOWN, UNKNOWN
    if inventory.gpu_status is GpuStatus.ABSENT:
        return "none", "0"
    if inventory.gpu_status is not GpuStatus.PRESENT:
        # The OS sees a card ggml cannot reach, or nothing could be read.
        return UNKNOWN, UNKNOWN
    # The discrete card the catalog prices against, else the integrated one.
    device = select_device(inventory.devices) or next(
        d for d in inventory.devices if d.type in (DeviceType.GPU, DeviceType.IGPU)
    )
    vram = vram_bucket(device.total_bytes) if device.total_bytes > 0 else UNKNOWN
    return gpu_vendor(device) or UNKNOWN, vram
