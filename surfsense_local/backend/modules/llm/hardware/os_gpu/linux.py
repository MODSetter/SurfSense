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


def reports_gpu(sysfs_root: Path = SYSFS_ROOT) -> bool | None:
    """True when a real card is present, False when none is, None when unknown.

    None rather than False if the directory is missing entirely: a kernel
    without DRM tells us nothing about the hardware, and guessing False would
    call a broken driver install a CPU only machine.
    """
    if not sysfs_root.is_dir():
        return None

    for card in sorted(sysfs_root.glob("card[0-9]*")):
        vendor = card / "device" / "vendor"
        try:
            value = vendor.read_text().strip().lower()
        except OSError:
            continue
        if value not in _VIRTUAL_VENDORS:
            return True
    # Either no cards at all, or only virtual ones. Both mean no GPU to reach.
    return False
