"""One reading of the machine, with the app's share of each resource beside it."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from modules.resource_usage.engines import Engine
from modules.resource_usage.gpu.reading import GpuReading


@dataclass(frozen=True)
class ProcessSample:
    pid: int
    engine: Engine
    # Of one core, as psutil reports it: four busy cores read 400.
    cpu_percent: float
    memory_bytes: int


@dataclass(frozen=True)
class SystemSample:
    cpu_percent: float
    logical_cores: int
    memory_total_bytes: int
    memory_available_bytes: int


@dataclass(frozen=True)
class Meter:
    total_bytes: int
    used_bytes: int
    # None where the platform cannot attribute usage to processes.
    app_bytes: int | None


@dataclass(frozen=True)
class Load:
    percent: float | None
    app_percent: float | None


@dataclass(frozen=True)
class GpuUsage:
    name: str
    unified_memory: bool
    memory: Meter
    load: Load


@dataclass(frozen=True)
class EngineUsage:
    engine: Engine
    processes: int
    cpu_percent: float
    memory_bytes: int
    gpu_memory_bytes: int | None
    gpu_percent: float | None


@dataclass(frozen=True)
class ResourceUsage:
    cpu: Load
    memory: Meter
    gpus: list[GpuUsage]
    engines: list[EngineUsage]


def assemble(
    processes: Sequence[ProcessSample],
    system: SystemSample,
    gpus: Sequence[GpuReading],
) -> ResourceUsage:
    cores = max(system.logical_cores, 1)
    used = system.memory_total_bytes - system.memory_available_bytes
    app_pids = {p.pid for p in processes}
    return ResourceUsage(
        cpu=Load(
            percent=system.cpu_percent,
            app_percent=_percent(sum(p.cpu_percent for p in processes) / cores),
        ),
        memory=Meter(
            total_bytes=system.memory_total_bytes,
            used_bytes=used,
            # Resident sizes count shared libraries once per process.
            app_bytes=min(sum(p.memory_bytes for p in processes), used),
        ),
        gpus=[_gpu(reading, app_pids) for reading in gpus],
        engines=[_engine(engine, processes, gpus, cores) for engine in Engine],
    )


def _gpu(reading: GpuReading, app_pids: set[int]) -> GpuUsage:
    app_bytes = _bytes_of(reading, app_pids)
    return GpuUsage(
        name=reading.name,
        unified_memory=reading.unified_memory,
        memory=Meter(
            total_bytes=reading.total_bytes,
            used_bytes=reading.used_bytes,
            app_bytes=None if app_bytes is None else min(app_bytes, reading.used_bytes),
        ),
        load=Load(
            percent=None
            if reading.busy_percent is None
            else _percent(reading.busy_percent),
            app_percent=_busy_of(reading, app_pids),
        ),
    )


def _engine(
    engine: Engine,
    processes: Sequence[ProcessSample],
    gpus: Sequence[GpuReading],
    cores: int,
) -> EngineUsage:
    own = [p for p in processes if p.engine is engine]
    pids = {p.pid for p in own}
    gpu_bytes = [b for g in gpus if (b := _bytes_of(g, pids)) is not None]
    gpu_busy = [b for g in gpus if (b := _busy_of(g, pids)) is not None]
    return EngineUsage(
        engine=engine,
        processes=len(own),
        cpu_percent=_percent(sum(p.cpu_percent for p in own) / cores),
        memory_bytes=sum(p.memory_bytes for p in own),
        gpu_memory_bytes=sum(gpu_bytes) if gpu_bytes else None,
        # Busy is a share of one device, so two devices are not summed.
        gpu_percent=max(gpu_busy) if gpu_busy else None,
    )


def _bytes_of(reading: GpuReading, pids: Iterable[int]) -> int | None:
    if reading.process_bytes is None:
        return None
    return sum(reading.process_bytes.get(pid, 0) for pid in pids)


def _busy_of(reading: GpuReading, pids: Iterable[int]) -> float | None:
    if reading.process_busy is None:
        return None
    return _percent(sum(reading.process_busy.get(pid, 0.0) for pid in pids))


def _percent(value: float) -> float:
    return min(max(value, 0.0), 100.0)
