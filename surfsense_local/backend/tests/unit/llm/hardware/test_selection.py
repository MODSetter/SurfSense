"""Choosing the device to budget against.

Both listings below are real: the Windows one from an RTX 3050 machine, the
macOS one from an M2. Each contains a trap that a plausible rule falls into.
"""

import pytest

from modules.llm.hardware import Device, DeviceType, select_device

pytestmark = pytest.mark.unit

MIB = 1024**2

# Measured on Windows. The integrated Radeon advertises 16 GB of system RAM
# against the discrete card's 6 GB.
WINDOWS = [
    Device("Vulkan0", "NVIDIA GeForce RTX 3050", DeviceType.GPU, 6002 * MIB, 5234 * MIB),
    Device("Vulkan1", "AMD Radeon(TM) Graphics", DeviceType.IGPU, 16198 * MIB, 16198 * MIB),
    Device("CPU", "AMD Ryzen 5 9600X", DeviceType.CPU, 31884 * MIB, 22750 * MIB),
]

# Measured on an M2. Note the Accelerate BLAS device, which is neither GPU nor CPU.
MACOS = [
    Device("MTL0", "Apple M2", DeviceType.GPU, 5461 * MIB, 5461 * MIB),
    Device("BLAS", "Accelerate", DeviceType.ACCEL, 0, 0),
    Device("CPU", "Apple M2", DeviceType.CPU, 8192 * MIB, 8192 * MIB),
]


def test_the_discrete_card_wins_over_a_larger_integrated_one() -> None:
    """Sorting by memory picks the 16 GB integrated chip and puts every layer on
    the slower device. ggml already orders backends by preference, so first wins."""
    assert select_device(WINDOWS).name == "Vulkan0"


def test_an_accelerator_is_never_mistaken_for_a_gpu() -> None:
    """Every Mac lists an Accelerate BLAS device, and it holds no weights."""
    assert select_device(MACOS).name == "MTL0"


def test_the_same_card_listed_once_per_backend_is_never_summed() -> None:
    """With CUDA and Vulkan both loaded a card appears twice, both typed GPU, so
    type filtering does not deduplicate. Summing reports 12 GB on a 6 GB card and
    every fit badge is then wrong in the dangerous direction."""
    doubled = [
        Device("CUDA0", "NVIDIA GeForce RTX 3050", DeviceType.GPU, 6143 * MIB, 5166 * MIB),
        Device("Vulkan0", "NVIDIA GeForce RTX 3050", DeviceType.GPU, 6002 * MIB, 5166 * MIB),
        Device("CPU", "AMD Ryzen 5 9600X", DeviceType.CPU, 31884 * MIB, 22750 * MIB),
    ]

    chosen = select_device(doubled)

    assert chosen.name == "CUDA0"
    assert chosen.total_bytes <= 6143 * MIB


def test_a_machine_with_no_gpu_says_so() -> None:
    """Not an error. It badges as running on the processor, and PARTIAL becomes
    unreachable because there is nothing to spill from."""
    assert select_device([MACOS[2]]) is None


def test_an_integrated_gpu_alone_is_not_budgeted_as_a_gpu() -> None:
    """A part carving from system RAM has no memory of its own to place layers in."""
    assert select_device([WINDOWS[1], WINDOWS[2]]) is None


def test_a_device_type_ggml_adds_later_is_not_a_gpu_and_is_not_a_crash() -> None:
    """ggml has grown this enum twice. An unknown integer must degrade to "not a
    GPU" rather than raise, because this runs on the first render."""
    listing = [Device("FUTURE0", "something new", DeviceType.parse(99), 8 * MIB, 8 * MIB)]

    assert select_device(listing) is None
