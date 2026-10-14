"""Page images of a rendered PDF, Word or PowerPoint version, so the agent can check its layout.

With Office support on, LibreOffice lays a Word file or deck out; otherwise,
or when it fails, Electron prints it with the in-app viewer's library.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from modules.agent.previews import docx_snapshots
from modules.agent.previews.page_images import PAGE_LIMIT, draw_pages
from modules.agent.thread_folder.layout import OUTPUTS, PREVIEWS
from modules.agent.thread_folder.path_budget import TOO_DEEP, fits
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.spec import FORMAT_NAMES
from modules.artifacts.script_documents.version import version_of
from modules.office_support import OfficeRunError, engine
from shared.config import get_storage_settings

# A Word or deck snapshot opens a window, lays the file out and prints it;
# past this the agent is better off going on without pages.
WORD_SNAPSHOT_SECONDS = 30
# Electron polls every 2 s and then prints; with less left it cannot answer.
WORD_SNAPSHOT_FLOOR_SECONDS = 3
# A warm conversion takes 1 to 5 s; past this, Electron's print is tried instead.
OFFICE_SECONDS = 60


@dataclass(frozen=True)
class Previews:
    """The page images written, why any are missing, and the LibreOffice that drew them, if one did."""

    pages: list[Path]
    reason: str | None = None
    drawn_by_office: str | None = None


def previews_for(
    artifact: Artifact, folder: Path, time_left: float = WORD_SNAPSHOT_SECONDS
) -> Previews:
    """Draw up to four pages or slides of a ready document version into a thread folder's outputs.

    Reads the artifact first and never touches its session, so a caller passes
    one whose files are loaded and holds no transaction: Word and PowerPoint
    wait for LibreOffice or Electron, within the caller's `time_left`, and
    SQLite would stay locked. A workbook has no pages to draw.
    """
    version = version_of(artifact.artifact_metadata)
    if version is None:
        raise ValueError(f"artifact {artifact.id} is not a document version")
    storage = get_storage_settings()
    pages = folder / OUTPUTS / PREVIEWS / f"{artifact.id}-v{version.number}"
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY), None
    )
    path = storage.data_dir / primary.storage_key if primary is not None else None
    if path is None or not path.is_file():
        return Previews([], "The document's file is missing, so no pages were drawn.")

    if artifact.format == "xlsx":
        return Previews([], "A workbook has no pages to draw.")
    if not fits(pages / f"page-{PAGE_LIMIT}.png"):
        return Previews([], TOO_DEEP.format(what="page previews"))
    if artifact.format == "pdf":
        pdf, drawn_by, notes = path.read_bytes(), None, []
    else:  # docx or pptx
        printed = _laid_out(artifact, path, time_left)
        if isinstance(printed, Previews):
            return printed
        pdf, drawn_by, notes = printed
    try:
        drawn = draw_pages(pdf, pages)
    except pypdfium2.PdfiumError as error:
        return Previews([], f"The pages could not be drawn: {error}")
    return Previews(drawn.pages, " ".join(notes + drawn.skipped) or None, drawn_by)


def _laid_out(
    artifact: Artifact, path: Path, time_left: float
) -> tuple[bytes, str | None, list[str]] | Previews:
    """A Word file's or deck's PDF, the LibreOffice that made it if one did, and
    why LibreOffice was passed over; or the Previews saying why there is none.

    LibreOffice first while Office support is on; Electron's print otherwise,
    or when LibreOffice is busy, out of time or fails.
    """
    began = time.monotonic()
    office = engine.office_engine()
    notes: list[str] = []
    if office is not None:
        try:
            deadline = began + min(OFFICE_SECONDS, time_left)
            return office.pdf_of(path, deadline=deadline), office.name, []
        except OfficeRunError as error:
            notes.append(str(error))
    time_left -= time.monotonic() - began
    if time_left < WORD_SNAPSHOT_FLOOR_SECONDS:
        name = FORMAT_NAMES[artifact.format]
        notes.append(f"This call had no time left to draw the {name}'s pages.")
        return Previews([], " ".join(notes))
    try:
        pdf = docx_snapshots.snapshots.snapshot(
            format=artifact.format,
            artifact_id=artifact.id,
            timeout=min(WORD_SNAPSHOT_SECONDS, time_left),
        )
    except docx_snapshots.SnapshotUnavailableError as error:
        return Previews([], " ".join([*notes, str(error)]))
    if notes:
        notes.append("The desktop app printed these pages instead.")
    return pdf, None, notes
