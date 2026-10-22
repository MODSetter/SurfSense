"""The machine in buckets: the card's maker from ggml's names, unknown where nothing says."""

import pytest

from modules.llm.hardware import Device, DeviceType, GpuStatus, SystemInventory
from modules.usage_statistics.hardware import hardware_buckets

pytestmark = pytest.mark.unit

GIB = 1024**3
CPU = Device("CPU", "Ryzen 7", DeviceType.CPU, 32 * GIB, 20 * GIB)


def inventory(
    *devices: Device, status: GpuStatus = GpuStatus.PRESENT
) -> SystemInventory:
    """A machine with these cards beside its processor."""
    return SystemInventory(devices=(*devices, CPU), gpu_status=status)


@pytest.mark.parametrize(
    ("device", "vendor"),
    [
        (Device("Vulkan0", "RTX 3050", DeviceType.GPU, 6 * GIB, 5 * GIB), "nvidia"),
        (
            Device("CUDA0", "NVIDIA GeForce RTX 4090", DeviceType.GPU, 24 * GIB, 0),
            "nvidia",
        ),
        (
            Device("Vulkan0", "AMD Radeon RX 7900 XTX", DeviceType.GPU, 24 * GIB, 0),
            "amd",
        ),
        (
            Device("Vulkan0", "Intel(R) Arc(TM) A770", DeviceType.GPU, 16 * GIB, 0),
            "intel",
        ),
        (Device("Metal", "Apple M2 Pro", DeviceType.GPU, 21 * GIB, 21 * GIB), "apple"),
        (
            Device("Vulkan0", "Mystery Accelerator", DeviceType.GPU, 8 * GIB, 0),
            "unknown",
        ),
    ],
)
def test_the_cards_maker_comes_from_the_names_ggml_gives_it(
    device: Device, vendor: str
) -> None:
    """Vulkan names a card by model alone, so a model family is enough to say whose."""
    assert hardware_buckets(inventory(device), 32 * GIB).gpu == vendor


def test_the_discrete_card_is_reported_over_an_integrated_one() -> None:
    """The one the model runtime prices against, as the catalog chooses it."""
    integrated = Device(
        "Vulkan1", "AMD Radeon(TM) Graphics", DeviceType.IGPU, 16 * GIB, 0
    )
    discrete = Device("Vulkan0", "RTX 3060", DeviceType.GPU, 12 * GIB, 11 * GIB)

    reading = hardware_buckets(inventory(integrated, discrete), 32 * GIB)

    assert (reading.gpu, reading.vram_gb) == ("nvidia", "12-23")


def test_an_integrated_card_alone_is_still_a_card() -> None:
    """A laptop with only integrated graphics has a GPU; its memory is what ggml says."""
    integrated = Device(
        "Vulkan0", "Intel(R) Iris(R) Xe Graphics", DeviceType.IGPU, 8 * GIB, 0
    )

    reading = hardware_buckets(inventory(integrated), 16 * GIB)

    assert (reading.gpu, reading.vram_gb, reading.ram_gb) == ("intel", "8-11", "16-31")


def test_no_card_is_none_with_no_memory_of_its_own() -> None:
    """The OS agrees there is no card, so this is a CPU-only machine, not an unknown one."""
    reading = hardware_buckets(inventory(status=GpuStatus.ABSENT), 8 * GIB)

    assert (reading.gpu, reading.vram_gb) == ("none", "0")


@pytest.mark.parametrize("status", [GpuStatus.BROKEN_INSTALL, GpuStatus.UNKNOWN])
def test_a_card_the_runtime_cannot_reach_is_unknown_not_none(status: GpuStatus) -> None:
    """The OS sees a card ggml cannot load, or nothing could be read: never guessed."""
    reading = hardware_buckets(inventory(status=status), 16 * GIB)

    assert (reading.gpu, reading.vram_gb) == ("unknown", "unknown")


def test_no_probe_at_all_is_unknown_and_no_memory_reading_is_no_hardware() -> None:
    """A failed probe leaves the card unknown; unreadable memory leaves nothing to send."""
    assert hardware_buckets(None, 16 * GIB).gpu == "unknown"
    assert hardware_buckets(inventory(status=GpuStatus.ABSENT), None) is None
