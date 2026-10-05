"""Page images of a rendered PDF, Word or PowerPoint version, so the agent can check its layout."""

from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from modules.agent.previews import docx_snapshots
from modules.agent.previews.page_images import draw_pages
from modules.agent.sources_folder import OUTPUTS
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.spec import FORMAT_NAMES
from modules.artifacts.script_documents.version import version_of
from shared.config import get_storage_settings

# A Word or deck snapshot opens a window, lays the file out and prints it;
# past this the agent is better off going on without pages.
WORD_SNAPSHOT_SECONDS = 30
# Electron polls every 2 s and then prints; with less left it cannot answer.
WORD_SNAPSHOT_FLOOR_SECONDS = 3


@dataclass(frozen=True)
class Previews:
    """The page images written, and why any are missing, in a sentence for the model."""

    pages: list[Path]
    reason: str | None = None


def previews_for(
    artifact: Artifact, time_left: float = WORD_SNAPSHOT_SECONDS
) -> Previews:
    """Draw up to four pages or slides of a ready document version into the agent's outputs.

    Reads the artifact first and never touches its session, so a caller passes
    one whose files are loaded and holds no transaction: Word and PowerPoint
    wait for Electron, up to WORD_SNAPSHOT_SECONDS or the caller's `time_left`,
    and SQLite would stay locked. A workbook has no pages to draw.
    """
    version = version_of(artifact.artifact_metadata)
    if version is None:
        raise ValueError(f"artifact {artifact.id} is not a document version")
    storage = get_storage_settings()
    folder = (
        storage.agent_working_dir(artifact.workspace_id)
        / OUTPUTS
        / "previews"
        / f"{artifact.id}-v{version.number}"
    )
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY), None
    )
    path = storage.data_dir / primary.storage_key if primary is not None else None
    if path is None or not path.is_file():
        return Previews([], "The document's file is missing, so no pages were drawn.")

    if artifact.format == "xlsx":
        return Previews([], "A workbook has no pages to draw.")
    if artifact.format == "pdf":
        pdf = path.read_bytes()
    else:  # docx or pptx, which Electron prints
        if time_left < WORD_SNAPSHOT_FLOOR_SECONDS:
            return Previews(
                [],
                f"This call had no time left to draw the "
                f"{FORMAT_NAMES[artifact.format]}'s pages.",
            )
        try:
            pdf = docx_snapshots.snapshots.snapshot(
                format=artifact.format,
                artifact_id=artifact.id,
                timeout=min(WORD_SNAPSHOT_SECONDS, time_left),
            )
        except docx_snapshots.SnapshotUnavailableError as error:
            return Previews([], str(error))

    try:
        drawn = draw_pages(pdf, folder)
    except pypdfium2.PdfiumError as error:
        return Previews([], f"The pages could not be drawn: {error}")
    return Previews(drawn.pages, " ".join(drawn.skipped) or None)
