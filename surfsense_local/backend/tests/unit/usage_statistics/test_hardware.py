"""The machine in buckets: the card's maker from ggml's names, unknown where nothing says."""

from collections.abc import Callable, Sequence

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


def os_lists(*names: str) -> Callable[[], Sequence[str] | None]:
    """The operating system's adapter list, as the summary's machine reads it."""
    return lambda: names


def os_cannot_say() -> Sequence[str] | None:
    """PowerShell, sysfs or the Mac could not answer."""
    return None


def os_never_asked() -> Sequence[str] | None:
    """Only a card the runtime cannot reach sends the summary to the OS."""
    raise AssertionError("the OS was asked about a card the runtime already named")


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
    reading = hardware_buckets(inventory(device), 32 * GIB, os_never_asked)

    assert (reading.gpu, reading.gpu_runtime) == (vendor, "reachable")


def test_the_discrete_card_is_reported_over_an_integrated_one() -> None:
    """The one the model runtime prices against, as the catalog chooses it."""
    integrated = Device(
        "Vulkan1", "AMD Radeon(TM) Graphics", DeviceType.IGPU, 16 * GIB, 0
    )
    discrete = Device("Vulkan0", "RTX 3060", DeviceType.GPU, 12 * GIB, 11 * GIB)

    reading = hardware_buckets(
        inventory(integrated, discrete), 32 * GIB, os_never_asked
    )

    assert (reading.gpu, reading.vram_gb) == ("nvidia", "12-23")


def test_an_integrated_card_alone_is_still_a_card() -> None:
    """A laptop with only integrated graphics has a GPU; its memory is what ggml says."""
    integrated = Device(
        "Vulkan0", "Intel(R) Iris(R) Xe Graphics", DeviceType.IGPU, 8 * GIB, 0
    )

    reading = hardware_buckets(inventory(integrated), 16 * GIB, os_never_asked)

    assert (reading.gpu, reading.vram_gb, reading.ram_gb, reading.gpu_runtime) == (
        "intel",
        "8-11",
        "16-31",
        "reachable",
    )


def test_no_card_is_none_with_no_memory_of_its_own() -> None:
    """The OS agrees there is no card, so this is a CPU-only machine, not an unknown one."""
    reading = hardware_buckets(
        inventory(status=GpuStatus.ABSENT), 8 * GIB, os_never_asked
    )

    assert (reading.gpu, reading.vram_gb, reading.gpu_runtime) == ("none", "0", "none")


@pytest.mark.parametrize(
    ("adapters", "vendor"),
    [
        (("NVIDIA GeForce RTX 3050 Laptop GPU",), "nvidia"),
        (("AMD Radeon RX 6600",), "amd"),
        (("Intel(R) Arc(TM) A770 Graphics",), "intel"),
        (("NVIDIA",), "nvidia"),
        (("Intel(R) UHD Graphics 630", "NVIDIA GeForce RTX 3060"), "nvidia"),
        (("AMD Radeon(TM) Graphics", "NVIDIA GeForce RTX 4060"), "nvidia"),
        (("Intel(R) UHD Graphics 770", "AMD Radeon RX 7600"), "amd"),
        (("Matrox G200eR2",), "unknown"),
        ((), "unknown"),
    ],
)
def test_a_card_the_runtime_cannot_reach_is_named_by_the_os(
    adapters: tuple[str, ...], vendor: str
) -> None:
    """ggml lists nothing to name or size, so the maker is the OS's and the memory unknown.

    Beside an integrated part, the discrete card's maker is the one reported.
    """
    reading = hardware_buckets(
        inventory(status=GpuStatus.BROKEN_INSTALL), 16 * GIB, os_lists(*adapters)
    )

    assert (reading.gpu, reading.vram_gb, reading.gpu_runtime) == (
        vendor,
        "unknown",
        "unreachable",
    )


def test_an_unreachable_card_the_os_will_not_name_is_unknown() -> None:
    """The OS said a card is there; a later listing that fails names no maker."""
    reading = hardware_buckets(
        inventory(status=GpuStatus.BROKEN_INSTALL), 16 * GIB, os_cannot_say
    )

    assert (reading.gpu, reading.vram_gb, reading.gpu_runtime) == (
        "unknown",
        "unknown",
        "unreachable",
    )


def test_a_machine_nothing_could_be_read_from_is_unknown_not_none() -> None:
    """Neither ggml nor the OS said anything: never guessed."""
    reading = hardware_buckets(
        inventory(status=GpuStatus.UNKNOWN), 16 * GIB, os_never_asked
    )

    assert (reading.gpu, reading.vram_gb, reading.gpu_runtime) == (
        "unknown",
        "unknown",
        "unknown",
    )


def test_no_probe_at_all_is_unknown_and_no_memory_reading_is_no_hardware() -> None:
    """A failed probe leaves the card unknown; unreadable memory leaves nothing to send."""
    reading = hardware_buckets(None, 16 * GIB, os_never_asked)

    assert (reading.gpu, reading.vram_gb, reading.gpu_runtime) == (
        "unknown",
        "unknown",
        "unknown",
    )
    assert (
        hardware_buckets(inventory(status=GpuStatus.ABSENT), None, os_never_asked)
        is None
    )
