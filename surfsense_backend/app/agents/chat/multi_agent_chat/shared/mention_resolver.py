"""Resolve @-mention chips to canonical virtual paths and substitute the
user-visible ``@title`` tokens with backtick-wrapped paths in the prompt
the agent sees.

The frontend's mention seam is a single discriminated-union list of
``{kind: "doc" | "folder", id, title, document_type?}`` chips (see
``surfsense_web/atoms/chat/mentioned-documents.atom.ts``). When a turn
reaches the backend stream task we have three needs that this module
centralises:

1. Map each chip to its canonical virtual path
   (``/documents/.../file.xml`` for docs, ``/documents/MyFolder/`` for
   folders) so the agent sees concrete filesystem locations instead of
   ambiguous ``@``-titles.
2. Substitute ``@title`` tokens in the user-typed text with backtick-
   wrapped paths so the path becomes part of the ``HumanMessage`` body
   the LLM consumes — without rewriting the persisted user message
   text (which keeps ``@title`` so chip rendering on reload is
   unchanged).
3. Surface the resolved id sets (docs + folders) to the priority
   middleware so it can render ``[USER-MENTIONED]`` priority entries
   without re-doing path resolution.

This is intentionally one module — see the architectural note in
``mention-paths-and-folders`` plan: previously the doc-resolution lived
inline in ``stream_new_chat`` and the folder mention had no resolution
at all. Centralising both behind a single ``resolve_mentions`` call
turns a leaky multi-field seam into a single deeper interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
)
from app.db import Document, Folder
from app.schemas.new_chat import MentionedDocumentInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedMention:
    """Canonical view of a single @-mention chip.

    ``virtual_path`` is the path the agent will see (no trailing slash
    for documents, trailing ``/`` for folders to match the convention
    used by ``KnowledgeTreeMiddleware``).
    """

    kind: str  # "doc" | "folder"
    id: int
    title: str
    virtual_path: str


@dataclass
class ResolvedMentionSet:
    """Aggregate result of resolving a turn's mention chips.

    ``token_to_path`` maps ``@title`` (the literal token the user typed
    and the editor emitted) to the canonical virtual path for that
    chip. It is produced longest-token-first so substitution mirrors
    ``parseMentionSegments`` on the frontend (a longer title like
    ``@Project Roadmap`` is never shadowed by a shorter prefix
    ``@Project``).

    ``mentioned_document_ids`` is an ordered, deduped list consumed by
    the priority middleware downstream — see
    ``KnowledgePriorityMiddleware._compute_priority_paths``.
    """

    mentions: list[ResolvedMention] = field(default_factory=list)
    token_to_path: list[tuple[str, str]] = field(default_factory=list)
    mentioned_document_ids: list[int] = field(default_factory=list)
    mentioned_folder_ids: list[int] = field(default_factory=list)


def _folder_virtual_path(folder_id: int, folder_paths: dict[int, str]) -> str:
    """Return ``/documents/Folder/Sub/`` for a folder id.

    Falls back to the documents root when the folder is missing from
    the index (deleted or in a different search space). Trailing slash
    matches ``KnowledgeTreeMiddleware`` (``/documents/MyFolder/``) so
    the agent's ``ls`` can dispatch on it as a directory.
    """
    base = folder_paths.get(folder_id, DOCUMENTS_ROOT)
    return f"{base}/" if not base.endswith("/") else base


async def resolve_mentions(
    session: AsyncSession,
    *,
    search_space_id: int,
    mentioned_documents: list[MentionedDocumentInfo] | None,
    mentioned_document_ids: list[int] | None = None,
    mentioned_folder_ids: list[int] | None = None,
) -> ResolvedMentionSet:
    """Resolve every @-mention chip on a turn into virtual paths.

    The function takes both the ``mentioned_documents`` discriminated
    list (chip metadata used for substitution + persistence) and the
    parallel id arrays (``mentioned_document_ids``,
    ``mentioned_folder_ids``) for two reasons:

    * Legacy clients that haven't migrated to the unified chip list
      still send the id arrays — we treat the union as authoritative.
    * The id arrays are the canonical input to
      ``KnowledgePriorityMiddleware`` (via ``SurfSenseContextSchema``);
      returning the deduped, validated lists lets the route forward
      them unchanged.

    Resolution is best-effort: a chip whose id no longer exists (e.g.
    document was deleted between mention and submit) is silently
    dropped. The agent still sees the user's original text, just
    without a backtick-path substitution for that chip.
    """
    chip_doc_ids: list[int] = []
    chip_folder_ids: list[int] = []
    chip_titles_by_id: dict[tuple[str, int], str] = {}
    if mentioned_documents:
        for chip in mentioned_documents:
            kind = chip.kind
            if kind == "folder":
                chip_folder_ids.append(chip.id)
            elif kind == "doc":
                chip_doc_ids.append(chip.id)
            chip_titles_by_id[(kind, chip.id)] = chip.title

    doc_id_pool: list[int] = list(
        dict.fromkeys(
            [
                *(mentioned_document_ids or []),
                *chip_doc_ids,
            ]
        )
    )
    folder_id_pool: list[int] = list(
        dict.fromkeys([*(mentioned_folder_ids or []), *chip_folder_ids])
    )

    if not doc_id_pool and not folder_id_pool:
        return ResolvedMentionSet()

    index = await build_path_index(session, search_space_id)

    doc_rows: dict[int, Document] = {}
    if doc_id_pool:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.id.in_(doc_id_pool),
            )
        )
        for row in result.scalars().all():
            doc_rows[row.id] = row

    folder_rows: dict[int, Folder] = {}
    if folder_id_pool:
        result = await session.execute(
            select(Folder).where(
                Folder.search_space_id == search_space_id,
                Folder.id.in_(folder_id_pool),
            )
        )
        for row in result.scalars().all():
            folder_rows[row.id] = row

    resolved: list[ResolvedMention] = []
    accepted_doc_ids: list[int] = []
    accepted_folder_ids: list[int] = []

    for doc_id in doc_id_pool:
        row = doc_rows.get(doc_id)
        if row is None:
            logger.debug(
                "mention_resolver: dropping doc id=%s (not found in space=%s)",
                doc_id,
                search_space_id,
            )
            continue
        title = chip_titles_by_id.get(("doc", doc_id), str(row.title or ""))
        path = doc_to_virtual_path(
            doc_id=row.id,
            title=str(row.title or "untitled"),
            folder_id=row.folder_id,
            index=index,
        )
        resolved.append(
            ResolvedMention(kind="doc", id=row.id, title=title, virtual_path=path)
        )
        accepted_doc_ids.append(row.id)

    for folder_id in folder_id_pool:
        row = folder_rows.get(folder_id)
        if row is None:
            logger.debug(
                "mention_resolver: dropping folder id=%s (not found in space=%s)",
                folder_id,
                search_space_id,
            )
            continue
        title = chip_titles_by_id.get(("folder", folder_id), str(row.name or ""))
        path = _folder_virtual_path(row.id, index.folder_paths)
        resolved.append(
            ResolvedMention(kind="folder", id=row.id, title=title, virtual_path=path)
        )
        accepted_folder_ids.append(row.id)

    token_to_path: list[tuple[str, str]] = []
    seen_tokens: set[str] = set()
    for mention in resolved:
        if not mention.title:
            continue
        token = f"@{mention.title}"
        if token in seen_tokens:
            continue
        seen_tokens.add(token)
        token_to_path.append((token, mention.virtual_path))
    token_to_path.sort(key=lambda pair: len(pair[0]), reverse=True)

    return ResolvedMentionSet(
        mentions=resolved,
        token_to_path=token_to_path,
        mentioned_document_ids=accepted_doc_ids,
        mentioned_folder_ids=accepted_folder_ids,
    )


def substitute_in_text(text: str, token_to_path: list[tuple[str, str]]) -> str:
    """Replace each ``@title`` token with a backtick-wrapped virtual path.

    Mirrors ``parseMentionSegments`` on the frontend: longest token
    first, single forward pass, no regex (titles can contain regex
    metacharacters). The substitution is idempotent for already-
    substituted text because the backtick-wrapped path no longer
    starts with ``@``.

    Empty / no-op cases short-circuit so callers can pass this through
    unconditionally without paying for a scan.
    """
    if not text or not token_to_path:
        return text

    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        matched: tuple[str, str] | None = None
        for token, path in token_to_path:
            if text.startswith(token, i):
                matched = (token, path)
                break
        if matched is None:
            out.append(text[i])
            i += 1
            continue
        token, path = matched
        out.append(f"`{path}`")
        i += len(token)
    return "".join(out)


__all__ = [
    "ResolvedMention",
    "ResolvedMentionSet",
    "resolve_mentions",
    "substitute_in_text",
]
