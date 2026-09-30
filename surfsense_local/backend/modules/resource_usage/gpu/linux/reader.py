import logging
from collections.abc import Set

from modules.resource_usage.gpu.linux.amdgpu import AmdgpuReader
from modules.resource_usage.gpu.linux.nvml import NvmlReader
from modules.resource_usage.gpu.reading import GpuReading

LOGGER = logging.getLogger(__name__)


class LinuxGpuReader:
    """Every vendor present; a machine can carry both."""

    def __init__(self) -> None:
        self._readers: list[NvmlReader | AmdgpuReader] = []
        try:
            nvml = NvmlReader()
            if nvml.found:
                self._readers.append(nvml)
        except (OSError, AttributeError) as error:
            LOGGER.debug("no NVML: %s", error)
        amdgpu = AmdgpuReader()
        if amdgpu.found:
            self._readers.append(amdgpu)

    def read(self, pids: Set[int]) -> list[GpuReading]:
        return [reading for reader in self._readers for reading in reader.read(pids)]
