"""The job eval's command line refuses a run count that would run nothing."""

import sys

import pytest
import run_job_eval

pytestmark = pytest.mark.unit


def test_runs_below_one_stop_before_the_pack_is_read(monkeypatch):
    """--runs 0 would read the pack and cases, run nothing and exit 0, which a sweep takes for
    success: argparse refuses it with its usage error instead."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_job_eval.py",
            "run",
            "--pack",
            "p",
            "--eval",
            "e",
            "--model",
            "openrouter:x",
            "--out",
            "o",
            "--runs",
            "0",
        ],
    )

    with pytest.raises(SystemExit) as stopped:
        run_job_eval.main()

    assert stopped.value.code == 2
