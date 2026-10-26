"""Whether Linux itself can see a graphics card.

Read from sysfs rather than by running a tool: `lspci` is not installed
everywhere, and every kernel with a DRM driver populates this directory.
"""

from pathlib import Path

SYSFS_ROOT = Path("/sys/class/drm")

# PCI vendor ids that mean a virtual display rather than a card that can compute.
# A guest with one of these has no GPU to be missing, so reporting one would
# turn every VM into a broken install.
_VIRTUAL_VENDORS = frozenset(
    {
        "0x1234",  # QEMU / Bochs
        "0x1af4",  # virtio
        "0x15ad",  # VMware
        "0x80ee",  # VirtualBox
        "0x1b36",  # QEMU QXL
    }
)

# sysfs gives a card's vendor id, not its name, so the maker stands in for one.
_VENDOR_NAMES = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}


def adapter_names(sysfs_root: Path = SYSFS_ROOT) -> list[str] | None:
    """Each real card's maker, its raw vendor id when unmapped; None without DRM."""
    if not sysfs_root.is_dir():
        return None

    names = []
    for card in sorted(sysfs_root.glob("card[0-9]*")):
        vendor = card / "device" / "vendor"
        try:
            value = vendor.read_text().strip().lower()
        except OSError:
            continue
        if value not in _VIRTUAL_VENDORS:
            names.append(_VENDOR_NAMES.get(value, value))
    return names


def reports_gpu(sysfs_root: Path = SYSFS_ROOT) -> bool | None:
    """True when a real card is present, False when none is, None when unknown.

    None rather than False if the directory is missing entirely: a kernel
    without DRM tells us nothing about the hardware, and guessing False would
    call a broken driver install a CPU only machine.
    """
    names = adapter_names(sysfs_root)
    # No cards at all, or only virtual ones, both mean no GPU to reach.
    return None if names is None else bool(names)
