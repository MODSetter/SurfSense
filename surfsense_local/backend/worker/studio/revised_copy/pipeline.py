"""Apply a version's edits, or accept or reject all, to a copy of its input, and shape a Built.

No model is asked and no database is open while the engine runs. The input is
the source's file for v1, read only, and the base version's primary after.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.engines import apply_operations, engine_for
from modules.artifacts.revised_copies.engines.package import PackageRefusedError
from modules.artifacts.revised_copies.formats import RevisableFormat, revisable_format
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.revised_copies.service import revised_title
from modules.artifacts.revised_copies.source_file import sha256_of
from modules.artifacts.revised_copies.versions import version_numbered
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import Document
from modules.documents.original_file import original_path
from worker.studio.script_document.deck_text import deck_text
from worker.studio.script_document.extracted_text import word_text
from worker.studio.script_document.workbook_summary import workbook_summary
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import file_stem

_TEXT = {"docx": word_text, "xlsx": workbook_summary, "pptx": deck_text}


class RevisionFailedError(RuntimeError):
    """The version cannot be made; the message is the reason the user and agent read."""


@dataclass(frozen=True)
class Prepared:
    input: Path
    # Set for v1: the source's bytes as the edits were checked against.
    expected_sha256: str | None
    format: RevisableFormat
    revision: dict[str, Any]
    title: str


@dataclass(frozen=True)
class Made:
    built: Built
    report: dict[str, Any] | None
    counts: dict[str, int] | None
    internal_comment_ids: list[str]
    external: bytes | None
    clean: bytes | None


def prepare(session: Session, artifact: Artifact) -> Prepared:
    """Where the version's input is, read while the session is open."""
    revision = revision_of(artifact.artifact_metadata)
    version = version_of(artifact.artifact_metadata)
    fmt = revisable_format(revision["source_name"]) if revision else None
    if revision is None or version is None or fmt is None:
        raise RevisionFailedError("This version keeps no revision to make.")
    if revision["base_number"] is None:
        source = session.get(Document, revision["derived_from_document_id"])
        path = original_path(source) if source is not None else None
        if path is None:
            raise RevisionFailedError(
                "The source file is no longer on disk, so the revised copy could "
                "not be made."
            )
        expected = revision["source_sha256"]
    else:
        path = version_numbered(
            session, artifact.workspace_id, version.root, revision["base_number"]
        )
        if path is None:
            raise RevisionFailedError(
                f"Version {revision['base_number']}, which this version is made "
                "from, is gone."
            )
        expected = None
    return Prepared(path, expected, fmt, revision, artifact.document.title)


def make(prepared: Prepared) -> Made:
    """Run the engine on a copy, in a scratch folder; nothing is written beside the input."""
    try:
        return _make(prepared)
    except PackageRefusedError as refused:
        raise RevisionFailedError(refused.message) from refused


def _make(prepared: Prepared) -> Made:
    suffix = prepared.format.suffix
    with TemporaryDirectory(prefix="surfsense-revise-") as scratch:
        folder = Path(scratch)
        copy = folder / f"input{suffix}"
        shutil.copyfile(prepared.input, copy)
        if (
            prepared.expected_sha256 is not None
            and sha256_of(copy) != prepared.expected_sha256
        ):
            raise RevisionFailedError(
                "The source file changed on disk after the edits were checked. Ask "
                "again, so they are checked against the file as it is now."
            )
        out = folder / f"revised{suffix}"
        report = _apply(prepared, copy, out)
        primary = out.read_bytes()
        stem = file_stem(revised_title(prepared.revision["source_name"]), "revised")
        built = Built(
            title=prepared.title,
            markdown="",
            primary=primary,
            primary_mime=prepared.format.mime,
            primary_filename=f"{stem}{suffix}",
        )
        if prepared.format.format != "docx":
            text = _TEXT[prepared.format.format](primary)
            built.markdown = text or f"# {built.title}"
            return Made(built, report, None, [], None, None)
        return _with_word_files(prepared, report, built, out, folder)


def _apply(prepared: Prepared, copy: Path, out: Path) -> dict[str, Any] | None:
    """The edit's report, as stored; deciding all changes has none."""
    action = prepared.revision["action"]
    if action == "accept_all":
        engine_for("docx").accept_all(copy, out)
        return None
    if action == "reject_all":
        engine_for("docx").reject_all(copy, out)
        return None
    report = apply_operations(
        prepared.format.format, copy, prepared.revision["operations"], out
    )
    if not report.saved:
        raise RevisionFailedError(nothing_saved(report))
    return report.as_metadata()


def _with_word_files(
    prepared: Prepared,
    report: dict[str, Any] | None,
    built: Built,
    out: Path,
    folder: Path,
) -> Made:
    """The counts, the file without internal comments when any are, and the clean file.

    The body is the clean file's text: the document as it reads with every change made.
    """
    word = engine_for("docx")
    internal = list(
        dict.fromkeys(
            [
                *prepared.revision.get("internal_comment_ids", []),
                *_new_internal_comments(prepared.revision["operations"], report),
            ]
        )
    )
    counted = word.counts(out)
    external_path: Path | None = None
    if internal:
        external_path = folder / "external.docx"
        word.external(out, external_path, internal)
    clean_path = folder / "clean.docx"
    word.accept_all(external_path or out, clean_path, drop_comments=True)
    clean = clean_path.read_bytes()
    built.markdown = word_text(clean) or f"# {built.title}"
    return Made(
        built,
        report,
        {"changes": counted.changes, "comments": counted.comments},
        internal,
        external_path.read_bytes() if external_path is not None else None,
        clean,
    )


def _new_internal_comments(
    operations: list[dict[str, Any]], report: dict[str, Any] | None
) -> list[str]:
    """The comment ids this edit added from operations marked internal."""
    if report is None:
        return []
    return [
        str(outcome["values"]["comment_id"])
        for outcome in report["ops"]
        if outcome["status"] == "applied"
        and "comment_id" in outcome["values"]
        and operations[outcome["index"]].get("internal") is True
    ]


def nothing_saved(report: Any) -> str:
    """Why an all-or-nothing edit saved nothing: its first refused operation, or the engine's note."""
    refused = [o for o in report.outcomes if o.status == "refused"]
    if refused:
        first = refused[0]
        return (
            f"Nothing was saved: operation #{first.index} was refused. {first.message}"
        )
    notes = " ".join(notice.message for notice in report.must_tell_user)
    return f"Nothing was saved. {notes}".strip()
