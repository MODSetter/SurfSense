"""Store prefix for a connected repo. Derived, not a user slug."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from app.knowledge_store.remote.exceptions import RemoteError

_FORGE_ROOT = {
    "github": "GitHub",
    "gitlab": "GitLab",
}

# The bijection round-trips text documents only. Binary formats (PDF, images)
# are left untouched on the remote
SYNCED_SUFFIXES = (".md", ".markdown", ".mdx", ".rst", ".txt")


def is_syncable(name: str) -> bool:
    """True for a path the folder sync round-trips (a tracked text document)."""
    return name.lower().endswith(SYNCED_SUFFIXES)


def mount(*, provider: str, full_name: str, sourcepath: str) -> str:
    """documents/{GitHub|GitLab}/{owner/repo}/{sourcepath}."""
    parts = ["documents", _FORGE_ROOT[provider], *_segments(full_name)]
    source = sourcepath.strip("/")
    if source:
        parts.extend(_segments(source))
    return "/".join(parts)


def full_name_from_url(url: str) -> str:
    """owner/repo from a forge URL, or the last segment of a local path."""
    if "://" not in url:
        name = Path(url.rstrip("/")).name
        return "/".join(_segments(name))
    path = urlsplit(url).path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    return "/".join(_segments(path))


def to_local(*, mount: str, rel: str) -> str:
    return f"{mount}/{_rel(rel)}"


def to_remote(*, sourcepath: str, rel: str) -> str:
    name = _rel(rel)
    prefix = sourcepath.strip("/")
    return f"{prefix}/{name}" if prefix else name


def rel_from_local(*, mount: str, path: str) -> str:
    prefix = f"{mount}/"
    if not path.startswith(prefix):
        raise RemoteError("unsafe_path", "path escapes the mount")
    return _rel(path[len(prefix) :])


def _rel(rel: str) -> str:
    name = "/".join(_segments(rel))
    if not is_syncable(name):
        raise RemoteError("unsafe_path", "sync is limited to text documents")
    return name


def _segments(value: str) -> list[str]:
    parts = [p for p in value.split("/") if p]
    if not parts or any(p in {".", ".."} for p in parts):
        raise RemoteError("unsafe_path", "path escapes the mount")
    return parts
