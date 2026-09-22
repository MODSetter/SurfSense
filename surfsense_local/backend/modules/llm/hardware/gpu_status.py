"""Whether this machine has a GPU the runtime can reach, and if not, why not.

ggml answers an empty device list with exit 0 on two very different machines: a
laptop with no graphics card, and a workstation whose backend library did not
ship. Measured on Windows and Linux with a working card and `ggml-cuda.dll`
staged but no cudart beside it, `--list-devices` prints `(none)` and exits 0,
and `GGML_BACKEND_DEBUG=1` changes nothing.

Badging the second as the first is the failure this module exists to stop. The
user sees every model marked as running on the processor, with no suggestion
that the card they bought is sitting idle because a file is missing.
"""

from collections.abc import Sequence
from enum import StrEnum

from modules.llm.hardware.devices import Device, DeviceType


class GpuStatus(StrEnum):
    """What to say about this machine's graphics hardware.

    `PRESENT` means ggml listed a GPU, which is not the same as the budget being
    priced against one: an integrated part counts here and is still skipped by
    `select_device`, because it carves from the same memory the host is using.
    This answers "is the runtime seeing the hardware", not "what will hold the
    layers".
    """

    PRESENT = "present"
    ABSENT = "absent"
    BROKEN_INSTALL = "broken_install"
    UNKNOWN = "unknown"


def classify(devices: Sequence[Device], os_reports_gpu: bool | None) -> GpuStatus:
    """Reconcile what ggml found with what the operating system can see."""
    if any(device.type in (DeviceType.GPU, DeviceType.IGPU) for device in devices):
        return GpuStatus.PRESENT

    if os_reports_gpu:
        return GpuStatus.BROKEN_INSTALL
    if os_reports_gpu is False:
        return GpuStatus.ABSENT

    # The OS could not say. A CPU device means ggml at least loaded and looked,
    # so no GPU is its genuine answer; nothing at all means the probe told us
    # nothing and neither will we.
    if any(device.type is DeviceType.CPU for device in devices):
        return GpuStatus.ABSENT
    return GpuStatus.UNKNOWN
