"""Refuse a staged set that is not synced text documents under {sourcepath}."""

from __future__ import annotations

from collections.abc import Sequence

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.paths import is_syncable


def check_staged(*, sourcepath: str, paths: Sequence[str]) -> None:
    prefix = sourcepath.strip("/")
    for path in paths:
        if not is_syncable(path) or not _under(prefix, path):
            raise RemoteError("would_delete_foreign", path)


def _under(prefix: str, path: str) -> bool:
    if not prefix:
        return True
    return path.startswith(prefix + "/")
