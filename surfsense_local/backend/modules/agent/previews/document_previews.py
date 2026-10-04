"""Page images of a rendered Word or PDF version, so the agent can check its layout."""

from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from modules.agent.previews import docx_snapshots
from modules.agent.previews.page_images import draw_pages
from modules.agent.sources_folder import OUTPUTS
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.artifacts.script_documents.version import version_of
from shared.config import get_storage_settings

# A Word snapshot opens a window, lays the document out and prints it; past
# this the agent is better off going on without pages.
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
    """Draw up to four pages of a ready document version into the agent's outputs.

    Reads the artifact first and never touches its session, so a caller passes
    one whose files are loaded and holds no transaction: a Word document waits
    for Electron, up to WORD_SNAPSHOT_SECONDS or the caller's `time_left`, and
    SQLite would stay locked.
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

    if artifact.format == "pdf":
        pdf = path.read_bytes()
    else:  # A document version is docx or pdf (script_documents.spec).
        if time_left < WORD_SNAPSHOT_FLOOR_SECONDS:
            return Previews(
                [], "This call had no time left to draw the Word document's pages."
            )
        try:
            pdf = docx_snapshots.snapshots.snapshot(
                artifact.id, timeout=min(WORD_SNAPSHOT_SECONDS, time_left)
            )
        except docx_snapshots.SnapshotUnavailableError as error:
            return Previews([], str(error))

    try:
        drawn = draw_pages(pdf, folder)
    except pypdfium2.PdfiumError as error:
        return Previews([], f"The pages could not be drawn: {error}")
    return Previews(drawn.pages, " ".join(drawn.skipped) or None)
