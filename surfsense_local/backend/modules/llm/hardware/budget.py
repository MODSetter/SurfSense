"""Assemble one device plus host memory into what the estimator subtracts.

Two modes, because the same subtraction answers two different questions.
**Capacity** prices a catalog: a shelf of models you might install later, which
must not move with whatever the machine happens to be doing right now. **Live**
decides a launch: this model, into this memory, in a moment. Pricing the catalog
against live free memory makes every large row read TOO_BIG whenever a browser
is open, which is a badge that lies in the direction users notice.
"""

from collections.abc import Sequence
from enum import StrEnum

from modules.llm.fit import HardwareBudget
from modules.llm.hardware.devices import Device, DeviceType
from modules.llm.hardware.selection import select_device

# llama.cpp's own `fit_params_target`, one GiB per device, read from
# common/common.h at b11050 and observed on both Vulkan and Metal. Not an
# estimate of the margin: the value the fitter will actually apply, and one we
# can pin through --fit-target rather than predict.
LLAMA_CPP_FIT_MARGIN_BYTES = 1024 * 1024 * 1024


class BudgetMode(StrEnum):
    """Which question the budget is answering."""

    CAPACITY = "capacity"  # pricing a catalog
    LIVE = "live"  # deciding a load


# What a host keeps for itself once a model is resident. Capacity mode assumes
# the rest is reclaimable, which is what makes a catalog stable between renders.
_HOST_RESERVE_BYTES = 2 * 1024 * 1024 * 1024


def build_budget(
    devices: Sequence[Device],
    ram_available_bytes: int,
    *,
    mode: BudgetMode = BudgetMode.LIVE,
    ram_total_bytes: int | None = None,
) -> HardwareBudget:
    """One device's memory plus the host's, never a sum across devices."""
    device = select_device(devices)
    ram = _host_memory(devices, ram_available_bytes, mode, ram_total_bytes)
    uma = any(d.type is DeviceType.GPU and _is_unified(d, devices) for d in devices)

    if device is None:
        return HardwareBudget(
            device_free_bytes=0,
            device_total_bytes=0,
            fit_reserve_bytes=LLAMA_CPP_FIT_MARGIN_BYTES,
            ram_available_bytes=ram,
            uma=uma,
            has_gpu=False,
        )

    return HardwareBudget(
        device_free_bytes=_device_free(device, uma, ram),
        device_total_bytes=device.total_bytes,
        fit_reserve_bytes=LLAMA_CPP_FIT_MARGIN_BYTES,
        ram_available_bytes=ram,
        uma=uma,
        has_gpu=True,
    )


def _is_unified(gpu: Device, devices: Sequence[Device]) -> bool:
    """A GPU sharing the CPU's description is sharing its memory.

    Apple Silicon reports the same part name for both, which is the cheap and
    reliable signal. It decides badge copy, not arithmetic.
    """
    return any(
        d.type is DeviceType.CPU and d.description == gpu.description for d in devices
    )


def _device_free(device: Device, uma: bool, host_memory: int) -> int:
    """How much the device can actually be given.

    On a discrete card this is the card's own figure: dedicated VRAM is a
    separate pool and its `free` really is live.

    On unified memory it is neither. Metal reports
    `recommendedMaxWorkingSetSize` as both total and free, a static number that
    does not move however busy the machine is, and the memory it describes is
    the same memory the OS and every other app are using. So **both** limits
    apply and the smaller governs: the working set is a ceiling Metal will not
    allocate past, and host memory is what is actually there to give.

    Spending the working set as though it were live is what sized a 28,672 token
    window on an 8 GB Mac with 2.3 GB reclaimable. The load paged and took 43
    seconds, which is long enough for title generation to time out at 30.
    """
    if not uma:
        return device.free_bytes
    return min(device.free_bytes, host_memory)


def _host_memory(
    devices: Sequence[Device],
    ram_available_bytes: int,
    mode: BudgetMode,
    ram_total_bytes: int | None,
) -> int:
    """Live memory as given, or capacity as total minus what the host keeps.

    The reserve is only meaningful against physical RAM. When nothing states
    that, the live reading is a **floor** rather than another figure to deduct
    from: subtracting twice reported 0 GB on a busy 8 GB machine and badged
    every model `Won't fit`, which is the confident-and-wrong failure this
    estimator exists to avoid.
    """
    if mode is BudgetMode.LIVE:
        return ram_available_bytes
    total = ram_total_bytes or _cpu_total(devices)
    if not total:
        # Nothing states physical RAM, so the live reading is the best floor
        # available. Deducting the reserve from it as well is what reported
        # 0 GB and is never right: the reserve assumes a total, not a remainder.
        return ram_available_bytes
    return max(0, total - _HOST_RESERVE_BYTES)


def _cpu_total(devices: Sequence[Device]) -> int:
    """Physical RAM. ggml restates it as `free` on several platforms, and that
    is exactly the number capacity mode wants."""
    return next((d.total_bytes for d in devices if d.type is DeviceType.CPU), 0)
