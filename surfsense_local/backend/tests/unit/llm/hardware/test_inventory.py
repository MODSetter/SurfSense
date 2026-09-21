"""Probing once, and saying what an empty answer means."""

from pathlib import Path

import pytest

from modules.llm.hardware import Device, DeviceType, GpuStatus, system_inventory

pytestmark = pytest.mark.unit

GIB = 1024**3
CPU = Device("CPU", "Ryzen 5", DeviceType.CPU, 32 * GIB, 22 * GIB)
DISCRETE = Device("Vulkan0", "RTX 3050", DeviceType.GPU, 6 * GIB, 5 * GIB)
NOWHERE = Path("/nowhere")


def test_a_probe_that_finds_a_card_reports_it_present() -> None:
    """The ordinary machine: devices and verdict travel together."""
    inventory = system_inventory(
        NOWHERE, probe=lambda _: [DISCRETE, CPU], os_gpu=lambda: True
    )

    assert inventory.devices == (DISCRETE, CPU)
    assert inventory.gpu_status is GpuStatus.PRESENT


def test_a_card_the_os_sees_and_the_runtime_does_not_is_reported_broken() -> None:
    """Phase 8.3: this must never be badged as a machine without a GPU."""
    inventory = system_inventory(NOWHERE, probe=lambda _: [CPU], os_gpu=lambda: True)

    assert inventory.gpu_status is GpuStatus.BROKEN_INSTALL


def test_a_runtime_that_will_not_load_at_all_is_the_same_diagnosis() -> None:
    """The strongest form of the same question. ggml could not be loaded, the
    operating system can see a card, so the install is what is wrong."""

    def raises(_: Path) -> list[Device]:
        raise OSError("no staged runtime")

    inventory = system_inventory(NOWHERE, probe=raises, os_gpu=lambda: True)

    assert inventory.devices == ()
    assert inventory.gpu_status is GpuStatus.BROKEN_INSTALL


def test_a_missing_runtime_on_a_machine_with_no_card_is_not_called_broken() -> None:
    """Nothing to reach and nothing reaching it. Two absences, not a fault."""

    def raises(_: Path) -> list[Device]:
        raise OSError("no staged runtime")

    inventory = system_inventory(NOWHERE, probe=raises, os_gpu=lambda: False)

    assert inventory.gpu_status is GpuStatus.ABSENT


def test_a_failed_probe_never_raises_out_of_the_inventory() -> None:
    """The catalog renders without a staged runtime, priced against the host."""

    def raises(_: Path) -> list[Device]:
        raise OSError("no staged runtime")

    assert system_inventory(NOWHERE, probe=raises, os_gpu=lambda: None).devices == ()
