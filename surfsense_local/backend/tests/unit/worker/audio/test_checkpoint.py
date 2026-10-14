"""The windows a job keeps as it goes, and which of them a later run resumes."""

from pathlib import Path

import pytest

from worker.ingestion.audio.checkpoint import (
    DoneWindow,
    append_window,
    resumable_windows,
)

pytestmark = pytest.mark.unit


def done(n: int, model_id: str = "m", intent: str = "auto") -> DoneWindow:
    """Window n as a run kept it."""
    return DoneWindow(n, n * 30.0, n * 30.0 + 24, f"window {n}", "en", model_id, intent)


def test_windows_written_by_the_same_model_and_language_resume(tmp_path: Path) -> None:
    """A yield or a retry picks up where the last run stopped."""
    path = tmp_path / "windows.jsonl"
    append_window(path, done(0))
    append_window(path, done(1))

    assert sorted(resumable_windows(path, "m", "auto")) == [0, 1]


@pytest.mark.parametrize(("model_id", "intent"), [("other", "auto"), ("m", "ja")])
def test_another_model_or_language_starts_over(
    tmp_path: Path, model_id: str, intent: str
) -> None:
    """Text from one model is not stitched to another's."""
    path = tmp_path / "windows.jsonl"
    append_window(path, done(0))

    assert resumable_windows(path, model_id, intent) == {}
    assert not path.exists()


def test_a_line_torn_by_a_crash_is_left_out_and_writing_goes_on(
    tmp_path: Path,
) -> None:
    """The app quit while a line was being written: that window is done again."""
    path = tmp_path / "windows.jsonl"
    append_window(path, done(0))
    with path.open("ab") as checkpoint:
        checkpoint.write(b'{"n": 1, "start_s": 30')
    append_window(path, done(2))

    assert sorted(resumable_windows(path, "m", "auto")) == [0, 2]
