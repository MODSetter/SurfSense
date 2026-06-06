"""Stateless path utilities shared by the middleware class and tool factories."""

from __future__ import annotations

import re

TEMP_PREFIX = "temp_"


def normalize_absolute_path(candidate: str) -> str:
    """Collapse slashes / backslashes and force an absolute path."""
    normalized = re.sub(r"/+", "/", candidate.strip().replace("\\", "/"))
    if not normalized:
        return "/"
    if normalized.startswith("/"):
        return normalized
    return f"/{normalized.lstrip('/')}"


def extract_mount_from_path(path: str, mounts: tuple[str, ...]) -> str | None:
    """Return the leading mount segment if it's in ``mounts``, else None."""
    rel = path.lstrip("/")
    if not rel:
        return None
    mount, _, _ = rel.partition("/")
    if mount in mounts:
        return mount
    return None


def local_parent_path(path: str) -> str:
    """Posix-style parent path (root = ``/``)."""
    rel = path.lstrip("/")
    if "/" not in rel:
        return "/"
    parent = rel.rsplit("/", 1)[0].strip("/")
    if not parent:
        return "/"
    return f"/{parent}"


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def is_ancestor_of(candidate: str, target: str) -> bool:
    """True iff ``candidate`` is a strict-or-equal ancestor of ``target``."""
    if candidate == "/":
        return target != "/"
    cand = candidate.rstrip("/")
    return target == cand or target.startswith(cand + "/")
