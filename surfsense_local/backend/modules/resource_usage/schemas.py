from pydantic import BaseModel

from modules.resource_usage.engines import Engine


class MeterRead(BaseModel):
    total_bytes: int
    # Everything in use, the app's share included.
    used_bytes: int
    # None where the platform cannot attribute usage to processes.
    app_bytes: int | None


class LoadRead(BaseModel):
    percent: float | None
    app_percent: float | None


class GpuUsageRead(BaseModel):
    name: str
    # Apple Silicon: the memory is system RAM, already in `memory`.
    unified_memory: bool
    memory: MeterRead
    load: LoadRead


class EngineUsageRead(BaseModel):
    engine: Engine
    processes: int
    # A share of the whole machine, not of one core.
    cpu_percent: float
    memory_bytes: int
    gpu_memory_bytes: int | None
    gpu_percent: float | None


class ResourceUsageRead(BaseModel):
    cpu: LoadRead
    memory: MeterRead
    gpus: list[GpuUsageRead]
    engines: list[EngineUsageRead]
