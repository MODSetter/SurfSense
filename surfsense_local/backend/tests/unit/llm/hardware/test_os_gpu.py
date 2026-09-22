"""Asking the operating system whether a graphics card is there at all.

Each platform's reader is tested directly rather than through the dispatcher,
because only one of the three can run on any given host and the dispatcher's
own job is one `sys.platform` comparison.
"""

import pytest

from modules.llm.hardware.os_gpu import linux, windows

pytestmark = pytest.mark.unit


def card(root, index: int, vendor: str) -> None:
    """One DRM card in a fake sysfs, as a kernel with a driver populates it."""
    device = root / f"card{index}" / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text(f"{vendor}\n")


def test_linux_reports_a_real_card(tmp_path) -> None:
    """0x10de is NVIDIA. A card the kernel bound a driver to."""
    card(tmp_path, 0, "0x10de")

    assert linux.reports_gpu(tmp_path) is True


def test_linux_does_not_count_a_virtual_display(tmp_path) -> None:
    """0x1234 is QEMU's display adapter. A VM has no card to be missing, so
    counting it would report every guest as a broken install."""
    card(tmp_path, 0, "0x1234")

    assert linux.reports_gpu(tmp_path) is False


def test_linux_sees_a_real_card_beside_a_virtual_one(tmp_path) -> None:
    """A passthrough guest: both are listed and only one can compute."""
    card(tmp_path, 0, "0x1234")
    card(tmp_path, 1, "0x1002")

    assert linux.reports_gpu(tmp_path) is True


def test_linux_with_no_cards_at_all_says_so(tmp_path) -> None:
    """A headless server. Nothing is wrong with it."""
    assert linux.reports_gpu(tmp_path) is False


def test_a_kernel_without_drm_admits_it_cannot_say(tmp_path) -> None:
    """No directory means no information, and guessing False here would call a
    broken driver install a machine without a card."""
    assert linux.reports_gpu(tmp_path / "absent") is None


def test_windows_lists_the_real_adapters() -> None:
    """What `Win32_VideoController` prints, one name per line."""
    output = "NVIDIA GeForce RTX 3050\nAMD Radeon(TM) Graphics\n"

    assert windows.parse_adapters(output) == [
        "NVIDIA GeForce RTX 3050",
        "AMD Radeon(TM) Graphics",
    ]


def test_windows_drops_the_virtual_display_the_measured_machine_carried() -> None:
    """The RTX 3050 box had a Parsec adapter beside its two real GPUs. Counting
    it would report a card on a machine that has none."""
    output = "Parsec Virtual Display Adapter\nMicrosoft Basic Display Adapter\n"

    assert windows.parse_adapters(output) == []


def test_windows_keeps_a_card_whose_name_merely_mentions_a_vendor() -> None:
    """The filter is on what the adapter is, not on who made it."""
    output = "Parsec Virtual Display Adapter\nIntel(R) Arc(TM) A770 Graphics\n"

    assert windows.parse_adapters(output) == ["Intel(R) Arc(TM) A770 Graphics"]
