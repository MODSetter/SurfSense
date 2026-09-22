"""Which device the catalog prices against.

One device, never a sum. The same physical card appears once per loaded backend
and an integrated GPU can advertise more memory than a discrete one, so both
"largest" and "total" are wrong in the direction that tells users a model fits
when it cannot.
"""

from collections.abc import Sequence

from modules.llm.hardware.devices import Device, DeviceType


def select_device(devices: Sequence[Device]) -> Device | None:
    """The first device ggml types as a discrete GPU, or None.

    First rather than largest: ggml already orders backends by preference, so
    taking the first is also backend selection. Sorting by memory picks a 16 GB
    integrated chip over a 6 GB discrete card and places every layer on the
    slower of the two.
    """
    return next((d for d in devices if d.type is DeviceType.GPU), None)
