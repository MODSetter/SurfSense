"""Where a thread's figures and source pages go for `read` to open them."""

import os
from pathlib import Path

from modules.agent.thread_folder.layout import FIGURES, PAGES, SOURCES


def page_image_path(folder: Path, document_id: int, page: int) -> Path:
    """`sources/pages/<id>-p<n>.png` in the thread's folder."""
    pages = folder / SOURCES / PAGES
    pages.mkdir(parents=True, exist_ok=True)
    return pages / f"{document_id}-p{page}.png"


def show_figure(folder: Path, name: str, png: Path) -> str:
    """Copy a source's figure into the thread's folder; its path from that folder."""
    figures = folder / SOURCES / FIGURES
    figures.mkdir(parents=True, exist_ok=True)
    data = png.read_bytes()
    path = figures / f"{name}.png"
    if not _holds(path, data):
        partial = path.with_name(f".{path.name}.partial")
        partial.write_bytes(data)
        os.replace(partial, path)
    return f"{SOURCES}/{FIGURES}/{path.name}"


def _holds(path: Path, data: bytes) -> bool:
    try:
        return path.stat().st_size == len(data) and path.read_bytes() == data
    except FileNotFoundError:
        return False
