"""The accelerator's own statistics, as `ioreg -c IOAccelerator` prints them."""

import re
from dataclasses import dataclass

_NODE = re.compile(r"^\+-o ", re.MULTILINE)
_MODEL = re.compile(r'"model" = "([^"]+)"')
_STATISTICS = re.compile(r'"PerformanceStatistics" = \{([^}]*)\}')
# The closing quote right after "memory" skips "In use system memory (driver)".
_IN_USE = re.compile(r'"In use system memory"=(\d+)')
_BUSY = re.compile(r'"Device Utilization %"=(\d+)')


@dataclass(frozen=True)
class AcceleratorStatistics:
    name: str
    in_use_bytes: int
    busy_percent: float | None


def parse(listing: str) -> list[AcceleratorStatistics]:
    gpus = []
    for node in _NODE.split(listing):
        statistics = _STATISTICS.search(node)
        in_use = _IN_USE.search(statistics[1]) if statistics else None
        if statistics is None or in_use is None:
            continue
        model = _MODEL.search(node)
        busy = _BUSY.search(statistics[1])
        gpus.append(
            AcceleratorStatistics(
                name=model[1] if model else "Apple GPU",
                in_use_bytes=int(in_use[1]),
                busy_percent=float(busy[1]) if busy else None,
            )
        )
    return gpus
