from collections.abc import Set

from modules.resource_usage.gpu.reading import GpuReading
from modules.resource_usage.gpu.windows.adapters import list_adapters
from modules.resource_usage.gpu.windows.counters import readings
from modules.resource_usage.gpu.windows.pdh import CounterQuery, RawValue

_ADAPTER_MEMORY = r"\GPU Adapter Memory(*)\Dedicated Usage"
_PROCESS_MEMORY = r"\GPU Process Memory(*)\Dedicated Usage"
_ENGINE_BUSY = r"\GPU Engine(*)\Utilization Percentage"
_COUNTERS = [_ADAPTER_MEMORY, _PROCESS_MEMORY, _ENGINE_BUSY]


class WindowsGpuReader:
    def __init__(self) -> None:
        # Listed once: a card does not come and go while the app runs.
        self._adapters = list_adapters()
        # Raises here, where the caller falls back, if the counters are missing.
        with CounterQuery(_COUNTERS):
            pass
        self._previous_busy: dict[str, RawValue] = {}

    def read(self, pids: Set[int]) -> list[GpuReading]:
        """Every process on every card: the counters cost the same either way."""
        with CounterQuery(_COUNTERS) as query:
            current = query.raw(_ENGINE_BUSY)
            busy = {
                name: rate
                for name, value in current.items()
                if (previous := self._previous_busy.get(name)) is not None
                and (rate := query.rate(_ENGINE_BUSY, value, previous)) is not None
            }
            self._previous_busy = current
            return readings(
                self._adapters,
                query.bytes(_ADAPTER_MEMORY),
                query.bytes(_PROCESS_MEMORY),
                # Empty on the first sample, which has nothing to pair with.
                busy,
            )
