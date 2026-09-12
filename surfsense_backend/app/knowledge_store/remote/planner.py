"""3-way plan for the markdown bijection. No git."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileChange:
    """One path in the bijection: bytes to write, or None to delete."""

    path: str
    content: bytes | None


@dataclass(frozen=True)
class SyncPlan:
    """Local store writes that make local match the 3-way result."""

    apply_local: tuple[FileChange, ...]


@dataclass(frozen=True)
class SyncConflict:
    """Same path changed on both sides; apply nothing."""

    paths: tuple[str, ...]


def plan(
    *,
    base: dict[str, bytes],
    local: dict[str, bytes],
    remote: dict[str, bytes],
) -> SyncPlan | SyncConflict:
    """Take remote when local still matches base. Conflict if both changed."""
    apply: list[FileChange] = []
    conflicts: list[str] = []
    for path in sorted(set(base) | set(local) | set(remote)):
        b = base.get(path)
        l = local.get(path)
        r = remote.get(path)
        if l == r:
            continue
        if l == b:
            apply.append(FileChange(path, r))
            continue
        if r == b:
            continue
        conflicts.append(path)
    if conflicts:
        return SyncConflict(paths=tuple(conflicts))
    return SyncPlan(apply_local=tuple(apply))
