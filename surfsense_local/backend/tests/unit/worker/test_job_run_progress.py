"""A run's progress: the total as soon as it is known, then the count at most every two seconds,
a write skipped for a lock tried again at the next row, and the last count kept for the end."""

import pytest

from worker.studio.job_run.progress import RunProgress

pytestmark = pytest.mark.unit


class Clock:
    """Seconds the test moves on by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_the_total_is_written_at_once_and_rows_at_most_every_two_seconds() -> None:
    """A row inside two seconds of the last write waits for a later one."""
    written: list[tuple[int, int]] = []
    clock = Clock()
    progress = RunProgress(
        lambda done, total: written.append((done, total)) or True, clock
    )

    for at, done in ((0.0, 0), (0.5, 1), (1.9, 2), (2.0, 3), (3.0, 4), (4.1, 5)):
        clock.now = at
        progress.on_row(done, 10)

    assert written == [(0, 10), (3, 10), (5, 10)]


def test_a_skipped_write_is_tried_again_at_the_next_row() -> None:
    """The database was locked twice; the third try gets through, and the next row waits."""
    tried: list[tuple[int, int]] = []
    gets_through = [False, False, True, True]
    clock = Clock()

    def write(done: int, total: int) -> bool:
        tried.append((done, total))
        return gets_through.pop(0)

    progress = RunProgress(write, clock)
    for at, done in ((0.0, 0), (0.1, 1), (0.2, 2), (0.3, 3)):
        clock.now = at
        progress.on_row(done, 4)

    assert tried == [(0, 4), (1, 4), (2, 4)]


def test_last_keeps_every_count_written_or_not() -> None:
    """The run's final write takes the last count, though the row itself was not written."""
    written: list[int] = []
    progress = RunProgress(lambda done, _total: written.append(done) or True, Clock())
    assert progress.last is None

    for done in range(4):
        progress.on_row(done, 3)

    assert written == [0]
    assert progress.last == {"done": 3, "total": 3}
