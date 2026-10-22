"""Which company made a device ggml lists, read from the names ggml gives it."""

import re

from modules.llm.hardware import Device

# Checked in order, against the description and then the backend's device name.
# Vulkan names a card by its model alone ("RTX 3050"), so model families count.
_VENDORS = (
    ("apple", re.compile(r"\bapple\b|^metal|^mtl\d", re.IGNORECASE)),
    (
        "nvidia",
        re.compile(r"nvidia|geforce|quadro|tesla|\brtx\b|\bgtx\b|^cuda", re.IGNORECASE),
    ),
    ("amd", re.compile(r"\bamd\b|radeon|instinct|^rocm|^hip", re.IGNORECASE)),
    ("intel", re.compile(r"intel|\barc\b|iris|uhd graphics|^sycl", re.IGNORECASE)),
)


def gpu_vendor(device: Device) -> str | None:
    """None when neither name says, which the report states as unknown."""
    for vendor, pattern in _VENDORS:
        if pattern.search(device.description) or pattern.search(device.name):
            return vendor
    return None
