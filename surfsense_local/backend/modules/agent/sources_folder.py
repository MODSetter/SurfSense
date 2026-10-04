"""The folder of extracted text the agent reads: one Markdown file per ready source.

opencode's own read, grep and glob work on files, so each source's Docling text
is laid out as one, and a figure the agent listed is copied to
`sources/figures/<name>.png` for `read` to show it. `sources/` is rebuilt from
the database before each turn and is SurfSense's; `outputs/` beside it is the
agent's and is never touched here.
"""

import os
import re
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures import parse_figure_name
from shared.config import get_storage_settings

SOURCES = "sources"
FIGURES = "figures"
OUTPUTS = "outputs"

# An artifact is an output, not a source; it reaches the agent through Studio.
_SOURCE_TYPES = (DocumentType.FILE, DocumentType.NOTE)
# Characters some file system refuses, and the separators that would make a title a path.
_UNSAFE = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
# Short enough that the id and extension still fit Windows' 255-character names.
_LONGEST_TITLE = 100


def sync_sources_folder(session: Session, workspace_id: int) -> Path:
    """Bring the sources folder in line with the workspace's ready sources.

    Returns the working folder opencode runs in, which holds `sources/` and
    `outputs/`.
    """
    folder = get_storage_settings().agent_working_dir(workspace_id)
    sources = folder / SOURCES
    sources.mkdir(parents=True, exist_ok=True)
    (folder / OUTPUTS).mkdir(exist_ok=True)

    # Every source's text is read to compare, on every turn (agent.md, Known gaps).
    ready = [
        document
        for document in _ready_sources(session, workspace_id)
        if document.content is not None
    ]
    wanted = {
        file_name(document.title, document.id): document.content.encode("utf-8")
        for document in ready
    }
    for existing in sources.iterdir():
        if existing.is_file() and existing.name not in wanted:
            existing.unlink()
    for name, text in wanted.items():
        path = sources / name
        if not _holds(path, text):
            _write_whole(path, text)
    _drop_figures_of_others(sources / FIGURES, {document.id for document in ready})
    return folder


def show_figure(workspace_id: int, name: str, png: Path) -> str:
    """Copy a source's figure where the agent can open it; its path from the agent's folder."""
    figures = get_storage_settings().agent_working_dir(workspace_id) / SOURCES / FIGURES
    figures.mkdir(parents=True, exist_ok=True)
    data = png.read_bytes()
    path = figures / f"{name}.png"
    if not _holds(path, data):
        _write_whole(path, data)
    return f"{SOURCES}/{FIGURES}/{path.name}"


def file_name(title: str, document_id: int) -> str:
    """The source's file in the folder: its title, made safe, and its id to keep it unique."""
    safe = _UNSAFE.sub("_", title).strip(" .")[:_LONGEST_TITLE] or "untitled"
    return f"{safe} [{document_id}].md"


def source_file_names(session: Session, workspace_id: int) -> dict[int, str]:
    """Each ready source's id and the name of its file here, without reading any text."""
    rows = session.execute(
        select(Document.id, Document.title).where(*_ready_source(workspace_id))
    ).all()
    return {row.id: file_name(row.title, row.id) for row in rows}


def _ready_sources(session: Session, workspace_id: int) -> Sequence[Document]:
    """The workspace's sources whose text ingestion has finished."""
    return session.scalars(select(Document).where(*_ready_source(workspace_id))).all()


def _ready_source(workspace_id: int) -> tuple[ColumnElement[bool], ...]:
    """What makes a document one of the workspace's sources the agent reads."""
    return (
        Document.workspace_id == workspace_id,
        Document.status == DocumentStatus.READY,
        Document.document_type.in_(_SOURCE_TYPES),
        Document.content.is_not(None),
    )


def _drop_figures_of_others(figures: Path, source_ids: set[int]) -> None:
    """A figure leaves with its source, as the source's text does."""
    if not figures.is_dir():
        return
    for existing in figures.iterdir():
        parsed = parse_figure_name(existing.stem)
        if existing.suffix != ".png" or parsed is None or parsed[0] not in source_ids:
            existing.unlink()


def _holds(path: Path, text: bytes) -> bool:
    """Whether the file already has exactly this text; the size answers most cases unread."""
    try:
        return path.stat().st_size == len(text) and path.read_bytes() == text
    except FileNotFoundError:
        return False


def _write_whole(path: Path, text: bytes) -> None:
    """Replace the file in one step, so a session reading it never sees half."""
    partial = path.with_name(f".{path.name}.partial")
    partial.write_bytes(text)
    os.replace(partial, path)
