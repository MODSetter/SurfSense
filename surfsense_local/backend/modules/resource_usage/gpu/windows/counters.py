"""One reading per card from the GPU counters' per-instance values.

Instances are named `luid_<luid>_phys_<n>` for a card, and
`pid_<pid>_luid_<luid>_phys_<n>[_eng_<n>_engtype_<kind>]` for a process on it.
"""

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence

from modules.resource_usage.gpu.carve_out import is_carve_out
from modules.resource_usage.gpu.reading import GpuReading
from modules.resource_usage.gpu.windows.adapters import Adapter

_INSTANCE = re.compile(
    r"^(?:pid_(?P<pid>\d+)_)?luid_(?P<luid>0x[0-9a-f]+_0x[0-9a-f]+)_phys_(?P<phys>\d+)"
    r"(?:_eng_(?P<engine>\d+)_engtype_.*)?$",
    re.IGNORECASE,
)


def readings(
    adapters: Sequence[Adapter],
    adapter_memory: Mapping[str, int],
    process_memory: Mapping[str, int],
    engine_busy: Mapping[str, float],
) -> list[GpuReading]:
    used: defaultdict[str, int] = defaultdict(int)
    for luid, _pid, _engine, value in _parsed(adapter_memory):
        used[luid] += value

    per_process: defaultdict[str, defaultdict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for luid, pid, _engine, value in _parsed(process_memory):
        if pid is not None:
            per_process[luid][pid] += value

    # Summed per engine across processes, then the busiest engine, as Task
    # Manager reads a card.
    engines: defaultdict[str, defaultdict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    process_busy: defaultdict[str, dict[int, float]] = defaultdict(dict)
    for luid, pid, engine, value in _parsed(engine_busy):
        if pid is None or engine is None:
            continue
        engines[luid][engine] += value
        process_busy[luid][pid] = max(process_busy[luid].get(pid, 0.0), value)

    # No rate at all is a first sample, not an idle card.
    measured = bool(engine_busy)
    return [
        GpuReading(
            name=adapter.name,
            total_bytes=adapter.dedicated_bytes,
            used_bytes=used[adapter.luid],
            busy_percent=(
                max(engines[adapter.luid].values(), default=0.0) if measured else None
            ),
            process_bytes=dict(per_process[adapter.luid]),
            process_busy=process_busy[adapter.luid] if measured else None,
        )
        for adapter in adapters
        if not is_carve_out(adapter.dedicated_bytes)
    ]


def _parsed(values: Mapping[str, float]):
    """(luid, pid, engine, value) for every instance whose name parses."""
    for instance, value in values.items():
        match = _INSTANCE.match(instance)
        if match is None:
            continue
        pid = match["pid"]
        engine = match["engine"]
        yield (
            match["luid"].lower(),
            int(pid) if pid else None,
            f"{match['phys']}:{engine}" if engine else None,
            value,
        )
