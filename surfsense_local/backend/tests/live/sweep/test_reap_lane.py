"""A lane's leftovers: what an earlier case left running is stopped before the next one starts."""

from pathlib import Path

import pytest

from tests.live.sweep.runner import reap_lane

pytestmark = pytest.mark.unit


class _Process:
    def __init__(self, pid: int, name: str, cmdline: list[str]) -> None:
        self.pid = pid
        self.info = {"name": name, "cmdline": cmdline}
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def test_an_orphaned_opencode_on_the_lane_s_ports_is_stopped(tmp_path: Path) -> None:
    """Its pytest died, so nothing else closes it, and it holds the lane's database."""
    lane = tmp_path / ".lanes" / "1"
    mine = _Process(1, "opencode.exe", ["opencode.exe", "serve", "--port", "30205"])
    other_lane = _Process(
        2, "opencode.exe", ["opencode.exe", "serve", "--port", "30305"]
    )
    from_folder = _Process(
        3, "python.exe", ["python", "-m", "pytest", f"--basetemp={lane}/tmp"]
    )
    unrelated = _Process(4, "Code.exe", ["Code.exe"])

    stopped = reap_lane(lane, 30200, lambda: [mine, other_lane, from_folder, unrelated])

    assert [p.killed for p in (mine, other_lane, from_folder, unrelated)] == [
        True,
        False,
        True,
        False,
    ]
    assert len(stopped) == 2
