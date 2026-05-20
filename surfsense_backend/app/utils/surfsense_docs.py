"""Utilities for SurfSense's built-in documentation index."""

from pathlib import PurePosixPath

DOCS_PUBLIC_ROOT = PurePosixPath("/docs")


def surfsense_docs_public_url(source: str) -> str:
    """Return the public docs route for an indexed documentation source path."""
    docs_path = PurePosixPath(source).with_suffix("")
    if docs_path.name == "index":
        docs_path = docs_path.parent
    return (DOCS_PUBLIC_ROOT / docs_path).as_posix()
