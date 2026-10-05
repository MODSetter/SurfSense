"""Where live runs leave their folders and the ledger."""

from pathlib import Path

import pytest

from tests.live.live_runs_dir import live_runs_dir

pytestmark = pytest.mark.unit


def test_runs_go_to_the_repos_ignored_folder_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """references/live-runs/, which .gitignore keeps out of the repo."""
    monkeypatch.delenv("SURFSENSE_LIVE_RUNS_DIR", raising=False)

    found = live_runs_dir()

    assert found.parts[-2:] == ("references", "live-runs")
    assert (found.parent.parent / "surfsense_local").is_dir()


def test_a_ladder_sweep_can_keep_its_runs_and_ledger_apart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SURFSENSE_LIVE_RUNS_DIR moves both."""
    monkeypatch.setenv("SURFSENSE_LIVE_RUNS_DIR", str(tmp_path / "ladder"))

    assert live_runs_dir() == tmp_path / "ladder"
