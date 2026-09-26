"""What this machine has, taken once and answered with a diagnosis.

The devices and the verdict about them travel together because they are read
together and are only meaningful together: an empty device list means nothing
until you know whether the operating system sees a card.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from modules.llm.hardware.devices import Device
from modules.llm.hardware.gpu_status import GpuStatus, classify
from modules.llm.hardware.os_gpu import os_reports_gpu
from modules.llm.hardware.probe_subprocess import probe_devices

logger = logging.getLogger(__name__)

Probe = Callable[[Path], Sequence[Device]]
OsGpu = Callable[[], bool | None]


@dataclass(frozen=True)
class SystemInventory:
    devices: tuple[Device, ...]
    gpu_status: GpuStatus


def system_inventory(
    library_dir: Path,
    *,
    probe: Probe = probe_devices,
    os_gpu: OsGpu = os_reports_gpu,
) -> SystemInventory:
    """Probe this machine, and say what an empty answer means.

    A probe that raises is the strongest form of the same question the empty
    list asks: ggml could not be loaded at all. If the operating system can see
    a card, that is a broken install and saying so is the whole point.

    `probe` and `os_gpu` are arguments so a test can state a machine rather than
    patch one into existence. Production passes neither.
    """
    try:
        devices = tuple(probe(library_dir))
    except OSError as error:
        logger.warning("could not probe devices: %s", error)
        devices = ()

    return SystemInventory(devices=devices, gpu_status=classify(devices, os_gpu()))
