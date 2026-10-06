"""What the revise tool answers once the version is ready: what changed, the opening text, and page previews."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.previews import previews_for
from modules.agent.previews.inline_images import inline_image
from modules.agent.tool_endpoint.render_document import (
    SLIDE_PREVIEWS_DIFFER,
    TEXT_CHARS,
    WORD_PREVIEWS_LEAVE_OUT,
)
from modules.agent.tool_endpoint.rendered_label import RenderedArtifact, first_line
from modules.agent.tool_endpoint.tool import InlineImage, ToolCallError, ToolResult
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.engines.report import Report
from modules.artifacts.revised_copies.revision import revision_of
from shared.config import get_storage_settings
from shared.db import is_locked

logger = logging.getLogger(__name__)

LOOK_AT_EVERY_PAGE = (
    "Look at every one before you answer; if one is wrong, revise again and look "
    "at the new version's pages too."
)
WORD_PREVIEWS_SHOW_CHANGES = (
    "The previews show tracked changes as Word does: insertions underlined, "
    "deletions struck through."
)


@dataclass(frozen=True)
class Revised:
    made: RenderedArtifact
    source_name: str
    base_number: int | None
    report: Report  # the checked run's, which the job repeated


def revised_result(
    session: Session, folder: Path, revised: Revised, deadline: float
) -> str | ToolResult:
    made = revised.made
    read = _read_ready(session, made.id, deadline)
    if read is None:
        return (
            f"{first_line(made)}\nIt is ready in Studio. Its text and previews "
            "could not be read while Studio was busy: tell the user it is ready, "
            "and do not revise it again."
        )
    artifact, text = read
    revision = revision_of(artifact.artifact_metadata) or {}
    images: tuple[InlineImage, ...] = ()
    if artifact.format == "xlsx":
        heading, body = "Its summary:", text
        check = (
            "A workbook has no pages: check the summary against what the user asked."
        )
    else:
        heading, body = "Its text begins:", _opening(text)
        check, images = _previews(artifact, made, folder, deadline)
    answer = "\n".join(
        [
            first_line(made),
            _what_changed(revised, revision),
            revised.report.as_text(),
            "",
            heading,
            body,
            "",
            check,
            f"To change it again, revise with artifact_id {made.id}.",
        ]
    )
    return ToolResult(answer, images) if images else answer


def _what_changed(revised: Revised, revision: dict) -> str:
    made = revised.made
    derived = revision.get("derived_from_document_id")
    line = f"Revised copy of source {derived} ({revised.source_name}), version {made.version}"
    if revised.base_number is not None:
        line += f" from version {revised.base_number}"
    report = revised.report
    line += f". {report.applied} of {len(report.outcomes)} operations applied"
    counts = revision.get("counts")
    if counts:
        line += (
            f"; {_count(counts['changes'], 'tracked change')}, "
            f"{_count(counts['comments'], 'comment')}"
        )
    return f"{line}."


def _read_ready(
    session: Session, artifact_id: int, deadline: float
) -> tuple[Artifact, str] | None:
    """The ready version and its text; None if the database stayed busy to the deadline."""
    while True:
        try:
            session.expire_all()
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                session.commit()
                raise ToolCallError(f"Artifact {artifact_id} was deleted once ready.")
            _ = artifact.files  # loaded now: the previews read them with no transaction
            text = artifact.document.content or ""
            session.commit()
            return artifact, text
        except OperationalError as error:
            session.rollback()
            if not is_locked(error):
                raise
            if time.monotonic() >= deadline:
                return None


def _opening(text: str) -> str:
    if len(text) <= TEXT_CHARS:
        return text
    return f"{text[:TEXT_CHARS]}… ({len(text) - TEXT_CHARS:,} more characters)"


def _previews(
    artifact: Artifact, made: RenderedArtifact, folder: Path, deadline: float
) -> tuple[str, tuple[InlineImage, ...]]:
    if not declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE):
        return "No page previews: the selected model cannot read images.", ()
    try:
        previews = previews_for(artifact, folder, time_left=deadline - time.monotonic())
    # The version is made; a preview that breaks must not send the model to make it again.
    except Exception:
        logger.exception("previews of artifact %s failed", artifact.id)
        return "No page previews: drawing them failed.", ()
    images: list[InlineImage] = []
    for page in sorted(previews.pages, key=lambda p: int(p.stem.split("-")[1])):
        try:
            images.append(inline_image(page))
        # A page that will not encode costs that page, never the made version.
        except Exception:
            logger.exception("page %s of artifact %s not attached", page, artifact.id)
    if not images:
        return f"No page previews: {previews.reason or 'none were drawn.'}", ()
    unit = "slide" if artifact.format == "pptx" else "page"
    caveats = (
        [WORD_PREVIEWS_SHOW_CHANGES, WORD_PREVIEWS_LEAVE_OUT]
        if artifact.format == "docx"
        else [SLIDE_PREVIEWS_DIFFER]
    )
    text = "\n".join(
        [
            f"{len(images)} {unit} previews of version {made.version} come with "
            "this result as images.",
            LOOK_AT_EVERY_PAGE,
            *([previews.reason] if previews.reason else []),
            *caveats,
        ]
    )
    return text, tuple(images)


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
