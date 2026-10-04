"""One sampler per process, rooted at the Electron shell when there is one."""

import logging
import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from api.config import get_settings
from modules.resource_usage.engines import Engine
from modules.resource_usage.gpu import GpuReader, NoGpuReader, platform_gpu_reader
from modules.resource_usage.sampler import ResourceSampler

LOGGER = logging.getLogger(__name__)


@lru_cache
def get_resource_sampler() -> ResourceSampler:
    shell = get_settings().shell_pid
    if shell is None:
        return ResourceSampler(os.getpid(), Engine.BACKEND, _gpu_reader())
    return ResourceSampler(shell, Engine.INTERFACE, _gpu_reader())


def _gpu_reader() -> GpuReader:
    try:
        return platform_gpu_reader()
    except Exception:
        LOGGER.warning("graphics usage unavailable on this machine", exc_info=True)
        return NoGpuReader()


ResourceSamplerDep = Annotated[ResourceSampler, Depends(get_resource_sampler)]
