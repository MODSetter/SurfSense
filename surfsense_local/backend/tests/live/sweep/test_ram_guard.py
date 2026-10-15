"""The RAM guard: how many cases may run at once."""

from tests.live.sweep.ram_guard import FLOOR_GB, RamGuard


def test_a_smaller_lane_given_stays_the_floor_once_peaks_are_learnt() -> None:
    """A sweep told its cases are small keeps that size, so more of them fit."""
    guard = RamGuard(lanes=6, lane_gb=1.25)
    for _ in range(10):
        guard.observe(0.9)
    assert guard.lane_gb == 1.25


def test_the_default_lane_keeps_the_ladder_floor() -> None:
    """Given no size, the lane never drops below what the ladder measured."""
    guard = RamGuard(lanes=6)
    for _ in range(10):
        guard.observe(0.9)
    assert guard.lane_gb == FLOOR_GB


def test_peaks_above_the_floor_size_the_lane() -> None:
    """Cases that turn out larger than the floor size the lane up."""
    guard = RamGuard(lanes=6, lane_gb=1.25)
    for _ in range(10):
        guard.observe(1.5)
    assert guard.lane_gb == 1.5
