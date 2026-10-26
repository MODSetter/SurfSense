"""Which company made a graphics card, read from the names ggml or the OS gives it."""

import re

from modules.llm.hardware import Device

# Checked in order against every name. Vulkan names a card by its model alone
# ("RTX 3050"), so model families count. The order also puts a discrete card's
# maker before the integrated part that came with the processor.
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
    return vendor_named(device.description, device.name)


def vendor_named(*names: str) -> str | None:
    """The first maker in pattern order that any of these names says, else None."""
    for vendor, pattern in _VENDORS:
        if any(pattern.search(name) for name in names):
            return vendor
    return None
