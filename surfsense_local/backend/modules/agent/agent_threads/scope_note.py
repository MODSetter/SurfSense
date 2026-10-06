"""The note telling the agent which sources a turn may use, and reading it back.

It goes to opencode as a synthetic part beside the user's words, so it lives in
the session and survives compaction; its first line is SurfSense's own tag, so
reading the thread back can take it out of the user's text and show the scope.
The thread's folder holds only its sources, so the note names no files.
"""

import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import SOURCES
from modules.documents.models import Document

_TAG = re.compile(r"\[surfsense-scope: (none|count=\d+|\d+(?:,\d+)*)\]")

# Past this many, the tag counts the sources: every turn's note stays in the
# session, and 5,000 ids are about 30 KB.
TAGGED_IDS = 200

_EARLIER = "Passages read earlier from other sources no longer apply."
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


def scope_note(ids: Sequence[int], indexing: int = 0) -> str:
    """The note for a turn's sources, already checked or resolved as a chat's are.

    `indexing` counts ticked sources not ready yet, so a ticked folder still
    being read is not called "no sources".
    """
    if not ids:
        selected = (
            "selected source is"
            if indexing == 1
            else f"{indexing} selected sources are"
        )
        why = _STILL_READING.format(selected=selected) if indexing else _NONE_SELECTED
        return f"[surfsense-scope: none]\n{why} {_EARLIER}"
    tag = (
        f"[surfsense-scope: {','.join(map(str, ids))}]"
        if len(ids) <= TAGGED_IDS
        else f"[surfsense-scope: count={len(ids)}]"
    )
    chose = (
        f"1 source for this chat; it is the file in {SOURCES}/. Use only that one."
        if len(ids) == 1
        else f"{len(ids)} sources for this chat; they are the files in {SOURCES}/. "
        "Use only those."
    )
    return f"{tag}\nThe user chose {chose} {_EARLIER}"


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
