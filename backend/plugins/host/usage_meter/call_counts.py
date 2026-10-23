"""Calls counted in memory until the meter writes them to the store."""

from collections.abc import Mapping
from dataclasses import dataclass

# The license of a call no check matched to one: no key, an unknown key, or a free plugin.
UNLICENSED = "unlicensed"


@dataclass(frozen=True)
class CallKey:
    day: str
    license: str
    plugin: str
    tool: str
    outcome: str


@dataclass
class Tally:
    calls: int = 0
    total_ms: int = 0


class CallCounts:
    """Touched only on the event loop, so taking them needs no lock."""

    def __init__(self) -> None:
        self._tallies: dict[CallKey, Tally] = {}

    def add(self, key: CallKey, ms: int) -> None:
        tally = self._tallies.setdefault(key, Tally())
        tally.calls += 1
        tally.total_ms += ms

    def take(self) -> dict[CallKey, Tally]:
        taken, self._tallies = self._tallies, {}
        return taken

    def put_back(self, taken: Mapping[CallKey, Tally]) -> None:
        """Counts a failed write took, kept for the next one."""
        for key, tally in taken.items():
            kept = self._tallies.setdefault(key, Tally())
            kept.calls += tally.calls
            kept.total_ms += tally.total_ms
