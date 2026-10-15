"""Where live runs leave their folders and the spend ledger."""

import os
from pathlib import Path

# references/live-runs/, which .gitignore keeps out of the repo.
_REPO_LIVE_RUNS = Path(__file__).resolve().parents[4] / "references" / "live-runs"


def live_runs_dir() -> Path:
    """SURFSENSE_LIVE_RUNS_DIR when set, so a sweep keeps its runs and ledger apart."""
    chosen = os.environ.get("SURFSENSE_LIVE_RUNS_DIR")
    return Path(chosen) if chosen else _REPO_LIVE_RUNS
