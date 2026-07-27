"""A revision's staged changes, recorded as intent verbs."""

from __future__ import annotations

from collections.abc import Callable


class RevisionDraft:
    """Changes staged for one revision."""

    def __init__(self) -> None:
        self._writes: dict[str, bytes] = {}
        self._removes: list[str] = []
        self._moves: list[tuple[str, str]] = []
        #: Recorded revision id, set on scope exit (``None`` when nothing changed).
        self.revision: str | None = None

    def write(self, path: str, content: bytes) -> None:
        """Create or replace ``path``."""
        self._writes[path] = content
        if path in self._removes:
            self._removes.remove(path)

    def remove(self, path: str) -> None:
        """Delete ``path``."""
        self._writes.pop(path, None)
        if path not in self._removes:
            self._removes.append(path)

    def move(self, src: str, dst: str) -> None:
        """Relocate ``src`` to ``dst``."""
        self._moves.append((src, dst))

    def to_change_set(
        self, read_current: Callable[[str], bytes | None]
    ) -> tuple[dict[str, bytes], list[str]]:
        """Collapse the staged verbs (moves included) into concrete writes/removes."""
        writes = dict(self._writes)
        removes = list(self._removes)
        for src, dst in self._moves:
            content = writes.pop(src, None)
            if content is None:
                content = read_current(src)
            if content is None:
                raise FileNotFoundError(f"cannot move missing path: {src}")
            writes[dst] = content
            removes.append(src)
        return writes, removes
