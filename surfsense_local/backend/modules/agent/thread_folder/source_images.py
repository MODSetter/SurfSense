"""Where a thread's figures and source pages go for `read` to open them."""

import os
from pathlib import Path

from modules.agent.thread_folder.layout import FIGURES, PAGES, SOURCES
from modules.agent.thread_folder.path_budget import TOO_DEEP, fits


class PathTooLongError(OSError):
    """A file the thread's folder sits too deep to hold, said in a sentence for the model."""


def page_image_path(folder: Path, document_id: int, page: int) -> Path:
    """`sources/pages/<id>-p<n>.png` in the thread's folder."""
    pages = folder / SOURCES / PAGES
    path = pages / f"{document_id}-p{page}.png"
    if not fits(path):
        raise PathTooLongError(TOO_DEEP.format(what="page images"))
    pages.mkdir(parents=True, exist_ok=True)
    return path


def show_figure(folder: Path, name: str, png: Path) -> str:
    """Copy a source's figure into the thread's folder; its path from that folder."""
    figures = folder / SOURCES / FIGURES
    path = figures / f"{name}.png"
    if not fits(path):
        raise PathTooLongError(TOO_DEEP.format(what="copies of images"))
    figures.mkdir(parents=True, exist_ok=True)
    data = png.read_bytes()
    if not _holds(path, data):
        # Shorter than the image's own name, so it fits wherever that does.
        partial = path.with_name(f".{name}~")
        partial.write_bytes(data)
        os.replace(partial, path)
    return f"{SOURCES}/{FIGURES}/{path.name}"


def _holds(path: Path, data: bytes) -> bool:
    try:
        return path.stat().st_size == len(data) and path.read_bytes() == data
    except FileNotFoundError:
        return False
