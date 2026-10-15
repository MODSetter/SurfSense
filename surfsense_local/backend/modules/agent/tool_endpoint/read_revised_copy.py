"""The read tool over a revised copy: its newest ready version as it reads now, which the next edit starts from."""

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.read_workbook import CELLS_SENTENCE, workbook_cells
from modules.agent.tool_endpoint.script_page import (
    OffsetOutOfRangeError,
    ScriptPage,
    page_of,
)
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.engines import engine_for
from modules.artifacts.revised_copies.engines.package import PackageRefusedError
from modules.artifacts.revised_copies.engines.word_marked_text import (
    MarkedText,
    marked_text,
)
from modules.artifacts.revised_copies.formats import revisable_format
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.revised_copies.versions import primary_path, versions_of
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus

_KINDS = {"docx": "a Word document", "xlsx": "a workbook", "pptx": "a PowerPoint deck"}
WORD_MARKS = (
    'Tracked changes are marked inline as <ins author="name">inserted text</ins> '
    'and <del author="name">deleted text</del>; [comment N] follows the text '
    "comment N is on. Quote text as it reads with the changes made: without the "
    "deleted text, the marks or the comment markers."
)


def read_revised_copy(
    session: Session, scope: TurnScope, named: Artifact, arguments: dict[str, Any]
) -> str:
    """Word with every author's changes and the comments, a workbook's cells, a deck's slides."""
    revision = revision_of(named.artifact_metadata) or {}
    source_name = str(revision.get("source_name", ""))
    found = revisable_format(source_name)
    version = version_of(named.artifact_metadata)
    assert version is not None  # every revised copy's version has one
    versions = versions_of(session, scope.workspace_id, version.root)
    ready = next(
        (v for v in versions if v.document.status is DocumentStatus.READY), None
    )
    path = primary_path(ready) if ready is not None else None
    if found is None or ready is None or path is None:
        raise ToolCallError(
            f"Artifact {named.id}'s revised copy has no ready version to read."
        )
    number = version_of(ready.artifact_metadata).number
    opening = (
        f'Artifact {ready.id}, version {number} of the revised copy of "{source_name}", '
        f"is {_KINDS[found.format]}."
    )
    revise = (
        "Make changes by calling surfsense_revise_document with artifact_id "
        f"{ready.id}."
    )
    edits = _edits_in_place(versions, number, found.format)
    deck = ready.document.content or ""
    internal = (revision_of(ready.artifact_metadata) or {}).get(
        "internal_comment_ids", []
    )
    session.rollback()  # reads only; a long file takes a while, past other writers' wait
    if found.format == "xlsx":
        return workbook_cells(
            path, f"{opening} {edits} {CELLS_SENTENCE} {revise}", arguments
        )
    if found.format == "pptx":
        return _paged(f"{opening} {edits} {revise}", "Slides", deck, arguments)
    marked = _marked(path, internal)
    counts = engine_for("docx").counts(path)
    held = (
        f"It holds {_count(counts.changes, 'tracked change')} and "
        f"{_count(counts.comments, 'comment')}, SurfSense's and any other author's."
    )
    return _paged(
        f"{opening} {held} {WORD_MARKS} {revise}", "Text", _word_text(marked), arguments
    )


def _edits_in_place(versions: list[Artifact], number: int, fmt: str) -> str:
    """Excel and PowerPoint keep no tracked changes, so the count is of the edits applied."""
    applied = 0
    for artifact in versions:
        version = version_of(artifact.artifact_metadata)
        report = (revision_of(artifact.artifact_metadata) or {}).get("report") or {}
        if (
            version is not None
            and version.number <= number
            and artifact.document.status is DocumentStatus.READY
        ):
            applied += int(report.get("applied") or 0)
    app = "Excel" if fmt == "xlsx" else "PowerPoint"
    return (
        f"It holds {_count(applied, 'edit')}, made in place: {app} keeps no tracked "
        "changes, and SurfSense adds no comments to it."
    )


def _marked(path: Path, internal: list[str]) -> MarkedText:
    try:
        return marked_text(path, internal)
    except PackageRefusedError as refused:
        raise ToolCallError(refused.message) from refused


def _word_text(marked: MarkedText) -> str:
    lines = list(marked.paragraphs)
    if marked.comments:
        lines += ["", "Comments:"]
        for note in marked.comments:
            internal = ", internal," if note.internal else ""
            anchor = f'on "{note.anchor}"' if note.anchor else "on no text"
            lines.append(
                f"Comment {note.id} by {note.author}{internal} {anchor}: {note.text}"
            )
    return "\n".join(lines)


def _paged(opening: str, heading: str, text: str, arguments: dict[str, Any]) -> str:
    offset = arguments.get("offset")
    offset = 1 if offset is None else offset
    page = _page(text or "(empty)", offset)
    rest = (
        ""
        if page.last == page.total
        else (
            f"\nThe text goes on past line {page.last}. Call surfsense_read_document "
            f"again with offset {page.last + 1} for the next lines."
        )
    )
    return "\n".join(
        [
            opening,
            "",
            f"{heading}, lines {page.first}-{page.last} of {page.total}:",
            page.text + rest,
        ]
    )


def _page(text: str, offset: object) -> ScriptPage:
    if isinstance(offset, int) and not isinstance(offset, bool):
        try:
            return page_of(text, offset)
        except OffsetOutOfRangeError:
            pass
    lines = page_of(text, 1).total
    raise ToolCallError(
        f"The text has {lines} lines: give an offset from 1 to {lines}, or leave it "
        "out to start at the top."
    )


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"
