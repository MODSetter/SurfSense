"""The note telling the agent which sources a turn may use, and reading it back.

It goes to opencode as a synthetic part beside the user's words, so it lives in
the session and survives compaction; its first line is SurfSense's own tag, so
reading the thread back can take it out of the user's text and show the scope.
"""

import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.agent.sources_folder import SOURCES, source_file_names
from modules.documents.models import Document

_TAG = re.compile(r"\[surfsense-scope: (none|\d+(?:,\d+)*)\]")

# Past this many, files are named by number: every turn's note stays in the session.
NAMED_FILES = 20

_USE_ONLY = (
    "Use only these. Do not search, open or cite any other file in "
    f"{SOURCES}/. If they do not hold what the request needs, say so and ask the "
    "user to select more sources."
)
_NONE_SELECTED = (
    "No sources are selected for this request. Do not search, open or cite any "
    f"file in {SOURCES}/. Answer from the conversation, or ask the user to select "
    "the sources to use."
)


def scope_note(session: Session, workspace_id: int, ids: Sequence[int]) -> str:
    """The note for a turn's sources, already checked or resolved as a chat's are."""
    if not ids:
        return f"[surfsense-scope: none]\n{_NONE_SELECTED}"
    tag = f"[surfsense-scope: {','.join(map(str, ids))}]"
    if len(ids) > NAMED_FILES:
        return "\n".join(
            [
                tag,
                f"The user selected {len(ids)} sources for this request: the files "
                f"in {SOURCES}/ whose number in brackets is on the line above.",
                _USE_ONLY,
            ]
        )
    files = source_file_names(session, workspace_id)
    # A ticked source with no text has no file; the tools still keep to it.
    named = [f"- {SOURCES}/{files[i]}" for i in ids if i in files]
    return "\n".join(
        [tag, "The user selected these sources for this request:", *named, _USE_ONLY]
    )


def is_scope_note(part: dict[str, Any]) -> bool:
    """Whether a message part is the note, never the user's own words."""
    return (
        part.get("type") == "text"
        and part.get("synthetic") is True
        and _TAG.match(part.get("text") or "") is not None
    )


def noted_scope(parts: list[dict[str, Any]]) -> list[int] | None:
    """The ticked ids a user message's note names; None when it carries none."""
    for part in parts:
        if is_scope_note(part):
            ids = _TAG.match(part["text"]).group(1)
            return [] if ids == "none" else [int(i) for i in ids.split(",")]
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
    """Give each turn's scope its sources' titles; a source deleted since drops out."""
    scopes = [turn["content"]["scope"] for turn in turns if "scope" in turn["content"]]
    titles = scope_titles(
        session, workspace_id, [i for scope in scopes for i in scope["document_ids"]]
    )
    for scope in scopes:
        kept = [i for i in scope["document_ids"] if i in titles]
        scope["document_ids"] = kept
        scope["titles"] = [titles[i] for i in kept]
