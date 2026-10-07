"""The note telling the agent which sources a turn may use, and reading it back.

It goes to opencode as a synthetic part beside the user's words, so it lives in
the session and survives compaction; its first line is SurfSense's own tag, so
reading the thread back can take it out of the user's text and show the scope.
The thread's folder holds only its sources; a few are named by path anyway, as a
small model guesses a file's name rather than looking for it.
"""

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import SOURCES
from modules.documents.models import Document

_TAG = re.compile(r"\[surfsense-scope: (none|count=\d+|\d+(?:,\d+)*)\]")

# Past this many, the tag counts the sources: every turn's note stays in the
# session, and 5,000 ids are about 30 KB.
TAGGED_IDS = 200
# Up to this many, the note names each source's file.
NAMED_PATHS = 20

_EARLIER = "Passages read earlier from other sources no longer apply."
# A small model repeats the note as the start of its answer.
_UNSAID = "SurfSense adds this note to the user's message; never repeat or quote it."
_HOW = "Open {them} with `read`, or search {them} with `surfsense_search_sources`."
_NONE_SELECTED = (
    "No sources are selected for this request. Do not search, open or cite any "
    f"file in {SOURCES}/. Answer from the conversation, or ask the user to select "
    "the sources to use."
)
_STILL_READING = (
    "The {selected} still being read, so none can be used "
    f"yet. Do not search, open or cite any file in {SOURCES}/. Answer from the "
    "conversation, or tell the user to send the request again once they are ready."
)


def scope_note(
    ids: Sequence[int],
    indexing: int = 0,
    paths: Mapping[int, PurePosixPath] | None = None,
) -> str:
    """The note for a turn's sources, already checked or resolved as a chat's are.

    `indexing` counts ticked sources not ready yet, so a ticked folder still
    being read is not called "no sources". `paths` places sources under
    `sources/`; up to NAMED_PATHS are named when each has one.
    """
    if not ids:
        selected = (
            "selected source is"
            if indexing == 1
            else f"{indexing} selected sources are"
        )
        why = _STILL_READING.format(selected=selected) if indexing else _NONE_SELECTED
        return f"[surfsense-scope: none]\n{why} {_EARLIER} {_UNSAID}"
    tag = (
        f"[surfsense-scope: {','.join(map(str, ids))}]"
        if len(ids) <= TAGGED_IDS
        else f"[surfsense-scope: count={len(ids)}]"
    )
    named = paths or {}
    if len(ids) <= NAMED_PATHS and all(i in named for i in ids):
        files = [f"`{SOURCES}/{named[i]}`" for i in ids]
        chose = (
            f"1 source for this chat, the file {files[0]}. Use only that one. "
            + _HOW.format(them="it")
            if len(ids) == 1
            else f"{len(ids)} sources for this chat, these files:\n"
            + "\n".join(f"- {file}" for file in files)
            + "\nUse only those. "
            + _HOW.format(them="them")
        )
    else:
        chose = (
            f"1 source for this chat; it is the file in {SOURCES}/. Use only that one."
            if len(ids) == 1
            else f"{len(ids)} sources for this chat; they are the files in {SOURCES}/. "
            "Use only those."
        )
    return f"{tag}\nThe user chose {chose} {_EARLIER} {_UNSAID}"


def shown_scope(
    session: Session, workspace_id: int, ids: Sequence[int]
) -> dict[str, Any]:
    """How the turn shows its sources: by title, or counted past TAGGED_IDS, as read back."""
    if len(ids) > TAGGED_IDS:
        return {"document_ids": [], "titles": [], "count": len(ids)}
    titles = scope_titles(session, workspace_id, ids)
    return {"document_ids": list(ids), "titles": [titles[i] for i in ids]}


def is_scope_note(part: dict[str, Any]) -> bool:
    """Whether a message part is the note, never the user's own words."""
    return (
        part.get("type") == "text"
        and part.get("synthetic") is True
        and _TAG.match(part.get("text") or "") is not None
    )


def noted_scope(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The scope a user message's note names, ids or a count; None when it carries none."""
    for part in parts:
        if is_scope_note(part):
            said = _TAG.match(part["text"]).group(1)
            if said == "none":
                return {"document_ids": []}
            if said.startswith("count="):
                return {"document_ids": [], "count": int(said.removeprefix("count="))}
            return {"document_ids": [int(i) for i in said.split(",")]}
    return None


def scope_titles(
    session: Session, workspace_id: int, ids: Sequence[int]
) -> dict[int, str]:
    """The titles of those of `ids` that still exist.

    Read workspace-wide and filtered here: a resolved folder can name more ids
    than SQLite takes as parameters.
    """
    wanted = set(ids)
    rows = session.execute(
        select(Document.id, Document.title).where(Document.workspace_id == workspace_id)
    ).all()
    return {i: title for i, title in rows if i in wanted}


def name_scopes(
    session: Session, workspace_id: int, turns: list[dict[str, Any]]
) -> None:
    """Give each turn's scope its sources' titles; a source deleted since drops out.

    A counted scope keeps its count and names nothing.
    """
    scopes = [turn["content"]["scope"] for turn in turns if "scope" in turn["content"]]
    titles = scope_titles(
        session, workspace_id, [i for scope in scopes for i in scope["document_ids"]]
    )
    for scope in scopes:
        kept = [i for i in scope["document_ids"] if i in titles]
        scope["document_ids"] = kept
        scope["titles"] = [titles[i] for i in kept]
