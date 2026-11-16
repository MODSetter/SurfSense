"""The windows a recording's job has transcribed, one JSON line each, appended
as each comes back: a yield, a retry or a restart carries on from here, so a
long file is never transcribed twice by the same model for the same language."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = ["DoneWindow", "append_window", "resumable_windows"]


@dataclass(frozen=True)
class DoneWindow:
    n: int
    start_s: float
    end_s: float
    text: str
    language: str | None
    # What wrote it: a checkpoint from another model or language is not resumed.
    model_id: str
    intent: str


def resumable_windows(path: Path, model_id: str, intent: str) -> dict[int, DoneWindow]:
    """The windows done by this model for this language, by number. Any other
    checkpoint is removed: the recording starts over."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return {}
    done: dict[int, DoneWindow] = {}
    for line in lines:
        try:
            window = DoneWindow(**json.loads(line))
        except (ValueError, TypeError):
            continue  # a line the last run was writing when it stopped
        if (window.model_id, window.intent) != (model_id, intent):
            path.unlink()
            return {}
        done[window.n] = window
    return done


def append_window(path: Path, window: DoneWindow) -> None:
    """Raises OSError when the disk is full."""
    line = json.dumps(asdict(window), ensure_ascii=False).encode() + b"\n"
    with path.open("a+b") as checkpoint:
        size = checkpoint.seek(0, 2)
        if size:
            checkpoint.seek(size - 1)
            if checkpoint.read(1) != b"\n":
                # A line torn when the last run stopped stays a line of its own.
                line = b"\n" + line
        checkpoint.write(line)
