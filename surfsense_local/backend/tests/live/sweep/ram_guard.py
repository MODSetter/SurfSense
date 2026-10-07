"""How many cases may run at once: free RAM, less what running cases may still take, must leave the desktop its floor.

A case that started a minute ago has not reached its peak (that comes at its
first render or print), so the guard reserves the rest of a lane for it;
without that, three cases started in quick succession all see the same free
memory and overcommit. 1.6 GB per lane was measured on the ladder from a
text-only model's runs, so it is the default floor: after ten cases the lane size
becomes the 95th percentile of the peaks actually seen, never below the floor.
"""

from dataclasses import dataclass, field

FLOOR_GB = 1.6
_LEARN_AFTER = 10


@dataclass
class RamGuard:
    lanes: int
    lane_gb: float = FLOOR_GB
    min_free_gb: float = 2.0
    peaks_gb: list[float] = field(default_factory=list)
    # The least a lane is sized at once peaks are learnt; the lane size given, unless that is above it.
    floor_gb: float | None = None

    def __post_init__(self) -> None:
        if self.floor_gb is None:
            self.floor_gb = min(FLOOR_GB, self.lane_gb)

    def may_start(self, available_gb: float, running_gb: list[float]) -> bool:
        """Whether one more case fits, given each running case's current working set."""
        if len(running_gb) >= self.lanes:
            return False
        unrealised = sum(max(0.0, self.lane_gb - now) for now in running_gb)
        return available_gb - unrealised - self.lane_gb >= self.min_free_gb

    def observe(self, peak_gb: float) -> str | None:
        """Learn from a finished case's peak; says so when the lane size changes."""
        self.peaks_gb.append(peak_gb)
        if len(self.peaks_gb) < _LEARN_AFTER:
            return None
        ordered = sorted(self.peaks_gb)
        p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
        sized = round(max(self.floor_gb or FLOOR_GB, p95), 2)
        if sized == self.lane_gb:
            return None
        before, self.lane_gb = self.lane_gb, sized
        return f"lane size {before} GB -> {sized} GB (p95 of {len(ordered)} peaks)"
