"""Samples the machine and the app's processes, keeping what a rate needs between calls.

CPU percent is a rate: psutil measures a process against its previous reading,
so the same Process objects have to outlive the request.
"""

import logging
import threading
from collections.abc import Set

import psutil

from modules.resource_usage.app_tree import branches
from modules.resource_usage.engines import Engine, engine_of
from modules.resource_usage.gpu import GpuReader
from modules.resource_usage.gpu.reading import GpuReading
from modules.resource_usage.parent_map import parent_map
from modules.resource_usage.snapshot import (
    ProcessSample,
    ResourceUsage,
    SystemSample,
    assemble,
)

LOGGER = logging.getLogger(__name__)

_GONE = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess)


class ResourceSampler:
    def __init__(self, root_pid: int, root_engine: Engine, gpu: GpuReader) -> None:
        self._root_pid = root_pid
        self._root_engine = root_engine
        self._gpu = gpu
        self._gpu_failed = False
        self._processes: dict[int, psutil.Process] = {}
        self._lock = threading.Lock()
        # The first reading only starts the interval the next one measures.
        psutil.cpu_percent(interval=None)

    def sample(self) -> ResourceUsage:
        with self._lock:
            tree = branches(parent_map(), self._root_pid, self._born)
            for pid in self._processes.keys() - tree.keys():
                del self._processes[pid]
            samples = [
                sample
                for pid, branch in tree.items()
                if (sample := self._sample(pid, self._engine(branch))) is not None
            ]
            memory = psutil.virtual_memory()
            system = SystemSample(
                cpu_percent=psutil.cpu_percent(interval=None),
                logical_cores=psutil.cpu_count() or 1,
                memory_total_bytes=memory.total,
                memory_available_bytes=memory.available,
            )
            return assemble(samples, system, self._read_gpus(tree.keys()))

    def _process(self, pid: int) -> psutil.Process:
        process = self._processes.get(pid)
        if process is None:
            process = self._processes[pid] = psutil.Process(pid)
        return process

    def _born(self, pid: int) -> float | None:
        try:
            return self._process(pid).create_time()
        except _GONE:
            return None

    def _engine(self, branch: int) -> Engine:
        if branch == self._root_pid:
            return self._root_engine
        try:
            return engine_of(self._process(branch).name())
        except _GONE:
            return Engine.INTERFACE

    def _sample(self, pid: int, engine: Engine) -> ProcessSample | None:
        try:
            process = self._process(pid)
            with process.oneshot():
                return ProcessSample(
                    pid=pid,
                    engine=engine,
                    cpu_percent=process.cpu_percent(interval=None),
                    # Resident size, Task Manager's working set: what is in RAM now.
                    memory_bytes=process.memory_info().rss,
                )
        except _GONE:
            return None

    def _read_gpus(self, pids: Set[int]) -> list[GpuReading]:
        """A driver that refuses costs the graphics rows, never the whole reading."""
        try:
            return self._gpu.read(pids)
        except Exception:
            if not self._gpu_failed:
                LOGGER.warning("could not read graphics usage", exc_info=True)
                self._gpu_failed = True
            return []
