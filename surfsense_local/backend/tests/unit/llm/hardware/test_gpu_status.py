"""Telling a machine with no GPU apart from one whose GPU cannot be reached.

ggml answers both with an empty device list and exit 0. Measured on Windows and
Linux with a working card and the backend library staged but its runtime
missing, `--list-devices` prints `(none)`, exits 0, and `GGML_BACKEND_DEBUG=1`
changes nothing.
"""

import pytest

from modules.llm.hardware import Device, DeviceType, GpuStatus, classify

pytestmark = pytest.mark.unit

GIB = 1024**3
DISCRETE = Device("Vulkan0", "RTX 3050", DeviceType.GPU, 6 * GIB, 5 * GIB)
INTEGRATED = Device("Vulkan1", "Radeon", DeviceType.IGPU, 16 * GIB, 16 * GIB)
CPU = Device("CPU", "Ryzen 5", DeviceType.CPU, 32 * GIB, 22 * GIB)


def test_a_card_the_runtime_can_see_is_simply_present() -> None:
    """The ordinary machine, and the only case with nothing to reconcile."""
    assert classify([DISCRETE, CPU], True) is GpuStatus.PRESENT


def test_no_card_and_the_os_agrees_is_a_cpu_only_machine() -> None:
    """An older laptop. Nothing is wrong with it and nothing should say so."""
    assert classify([CPU], False) is GpuStatus.ABSENT


def test_no_card_while_the_os_sees_one_is_a_broken_install() -> None:
    """The row this module exists for. Badging it CPU only tells a user their
    card does not work, when a file is missing from our own package."""
    assert classify([CPU], True) is GpuStatus.BROKEN_INSTALL


def test_an_integrated_part_counts_as_the_runtime_seeing_hardware() -> None:
    """It is skipped for pricing, because it carves from the host's memory, but
    the runtime did reach it, so nothing is broken and nothing should be said."""
    assert classify([INTEGRATED, CPU], True) is GpuStatus.PRESENT


def test_an_os_that_cannot_say_still_trusts_a_loaded_runtime() -> None:
    """ggml loaded and looked, and found only a processor. That is an answer."""
    assert classify([CPU], None) is GpuStatus.ABSENT


def test_nothing_from_either_side_is_admitted_rather_than_guessed() -> None:
    """The probe failed and the OS declined. Calling that CPU only would be
    inventing the one answer that reads as a verdict about the hardware."""
    assert classify([], None) is GpuStatus.UNKNOWN
