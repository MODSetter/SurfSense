"""The note telling the agent which sources the user named with `@` in this message.

A mirrored path rather than a title: a title is the user's or a file's own text, and
a small model guesses a file's name rather than looking for it. Its first line is
SurfSense's own tag, so reading the thread back can show what each message named.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.agent_threads.scope_note import UNSAID
from modules.agent.thread_folder.layout import SOURCES
from modules.artifacts.models import Artifact
from modules.documents.models import Document
from modules.folders.models import Folder
from modules.source_scope.schemas import MentionedSources

_TAG = re.compile(
    r"^\[surfsense-mentions: ((?:document|folder):\d+(?:,(?:document|folder):\d+)*)\]",
    re.MULTILINE,
)


@dataclass(frozen=True)
class NamedFile:
    path: PurePosixPath
    # A Studio or agent document: what `surfsense_read_document` takes.
    artifact_id: int | None = None


def mention_note(
    named: MentionedSources,
    files: Sequence[NamedFile],
    more: int,
    unreadable: int,
    nothing_ready: int,
) -> str | None:
    """`more` are readable but past the listed; `unreadable` have no text to read;
    `nothing_ready` are named sources or folders that gave the turn nothing."""
    tagged = [
        *(f"document:{i}" for i in named.document_ids),
        *(f"folder:{i}" for i in named.folder_ids),
    ]
    if not tagged:
        return None
    lines = [f"[surfsense-mentions: {','.join(tagged)}]"]
    if files or more:
        lines.append("The user named these sources in their message. Start from them.")
    lines += [
        f'- "{SOURCES}/{file.path}"'
        + (f" (artifact {file.artifact_id})" if file.artifact_id is not None else "")
        for file in files
    ]
    if more:
        lines.append(f"- and {more} more in {SOURCES}/")
    if unreadable:
        lines.append(
            f"{unreadable} more they named cannot be read as text; say so if the "
            "request needs it."
        )
    if nothing_ready:
        lines.append(
            f"{nothing_ready} of what they named has nothing ready to read; say so "
            "rather than answering from other sources."
        )
    lines.append(UNSAID)
    return "\n".join(lines)


def noted_mentions(notes: list[dict[str, Any]]) -> list[dict[str, str]] | None:
    """What a turn's notes say it named, by id; its reader names them."""
    for note in notes:
        if note.get("type") != "synthetic":
            continue
        if (tagged := _TAG.search(note.get("text") or "")) is not None:
            return [{"id": named} for named in tagged.group(1).split(",")]
    return None


def name_mentions(
    session: Session, workspace_id: int, turns: list[dict[str, Any]]
) -> None:
    """Give each turn's mentions what a chip shows; one deleted since drops out."""
    with_mentions = [t["content"] for t in turns if "mentions" in t["content"]]
    if not with_mentions:
        return
    ids = {m["id"] for content in with_mentions for m in content["mentions"]}
    shown = _documents(session, workspace_id, ids) | _folders(
        session, workspace_id, ids
    )
    for content in with_mentions:
        kept = [shown[m["id"]] for m in content["mentions"] if m["id"] in shown]
        if kept:
            content["mentions"] = kept
        else:
            del content["mentions"]


def _ids_of(ids: set[str], kind: str) -> list[int]:
    return [int(i.split(":")[1]) for i in ids if i.startswith(f"{kind}:")]


def _documents(
    session: Session, workspace_id: int, ids: set[str]
) -> dict[str, dict[str, str]]:
    rows = session.execute(
        select(Document.id, Document.title, Artifact.format)
        .outerjoin(Artifact, Artifact.document_id == Document.id)
        .where(
            Document.workspace_id == workspace_id,
            Document.id.in_(_ids_of(ids, "document")),
        )
    ).all()
    return {
        f"document:{row.id}": {
            "id": f"document:{row.id}",
            "type": f"artifact-{row.format}" if row.format else "source",
            "label": row.title,
        }
        for row in rows
    }


def _folders(
    session: Session, workspace_id: int, ids: set[str]
) -> dict[str, dict[str, str]]:
    rows = session.execute(
        select(Folder.id, Folder.name).where(
            Folder.workspace_id == workspace_id,
            Folder.id.in_(_ids_of(ids, "folder")),
        )
    ).all()
    return {
        f"folder:{row.id}": {
            "id": f"folder:{row.id}",
            "type": "source",
            "label": row.name,
        }
        for row in rows
    }
