"""attempts.jsonl: one line per finished attempt, appended and never rewritten, so a restarted sweep knows what is done."""

import json
import os
from pathlib import Path

from tests.live.sweep.attempt import Attempt


class AttemptLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> list[Attempt]:
        """Every attempt so far; a line torn by a kill mid-write is skipped."""
        if not self.path.is_file():
            return []
        attempts = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                attempts.append(Attempt.from_json(json.loads(line)))
            except (ValueError, TypeError):
                continue
        return attempts

    def append(self, attempt: Attempt) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(attempt.to_json(), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as log:
            # A line torn by an earlier kill must not swallow this one.
            if log.tell() and not self._ends_with_newline():
                log.write("\n")
            log.write(line + "\n")
            log.flush()
            os.fsync(log.fileno())

    def _ends_with_newline(self) -> bool:
        with self.path.open("rb") as log:
            log.seek(-1, os.SEEK_END)
            return log.read(1) == b"\n"
