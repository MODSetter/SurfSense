"""Postgres-backed virtual filesystem for the SurfSense agent (cloud mode).

The backend is **strictly conforming** to deepagents'
:class:`BackendProtocol`. It returns ``WriteResult`` / ``EditResult`` / list
shapes exactly as upstream expects (no extra fields). All side-state
plumbing — ``dirty_paths``, ``doc_id_by_path``, ``staged_dirs``,
``pending_moves``, ``files`` cache — is appended by the overridden tool
wrappers in :class:`SurfSenseFilesystemMiddleware` via ``Command.update``.

The backend never writes to Postgres. End-of-turn persistence is handled by
:class:`KnowledgeBasePersistenceMiddleware`. This module is purely a
read-side and a state-merging helper.
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import logging
import re
from datetime import UTC
from typing import Any

from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from deepagents.backends.utils import (
    create_file_data,
    file_data_to_string,
    format_read_response,
    perform_string_replacement,
    update_file_data,
)
from langchain.tools import ToolRuntime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.document_xml import build_document_xml
from app.agents.new_chat.path_resolver import (
    DOCUMENTS_ROOT,
    build_path_index,
    doc_to_virtual_path,
    virtual_path_to_doc,
)
from app.db import Chunk, Document, shielded_async_session

logger = logging.getLogger(__name__)

_TEMP_PREFIX = "temp_"
_GREP_MAX_TOTAL_MATCHES = 50
_GREP_MAX_PER_DOC = 5


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _is_under(child: str, parent: str) -> bool:
    """Return True iff ``child`` is at-or-under ``parent`` (directory semantics)."""
    if parent == "/":
        return child.startswith("/")
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def paginate_listing(
    infos: list[FileInfo],
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[FileInfo]:
    """Paginate a listing produced by :meth:`KBPostgresBackend.als_info`."""
    if offset < 0:
        offset = 0
    end: int | None
    end = None if limit is None or limit < 0 else offset + limit
    return list(infos[offset:end])


class KBPostgresBackend(BackendProtocol):
    """Lazy, read-only Postgres view for ``/documents/*`` virtual paths.

    The backend exposes a virtual ``/documents/`` namespace mirroring the
    ``Folder``/``Document`` graph. Reads materialize XML on first access and
    cache it via the overriding tool wrappers (NOT here). Writes never touch
    the DB — they return ``files_update`` deltas that the wrappers turn into
    Command updates, and the persistence middleware commits them at end of
    turn.
    """

    _IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})

    def __init__(self, search_space_id: int, runtime: ToolRuntime) -> None:
        self.search_space_id = search_space_id
        self.runtime = runtime

    @property
    def state(self) -> dict[str, Any]:
        return getattr(self.runtime, "state", {}) or {}

    # ------------------------------------------------------------------ helpers

    def _state_files(self) -> dict[str, Any]:
        return dict(self.state.get("files") or {})

    def _staged_dirs(self) -> list[str]:
        return list(self.state.get("staged_dirs") or [])

    def _pending_moves(self) -> list[dict[str, Any]]:
        return list(self.state.get("pending_moves") or [])

    def _kb_anon_doc(self) -> dict[str, Any] | None:
        anon = self.state.get("kb_anon_doc")
        return anon if isinstance(anon, dict) else None

    def _matched_chunk_ids(self, doc_id: int) -> set[int]:
        mapping = self.state.get("kb_matched_chunk_ids") or {}
        try:
            return set(mapping.get(doc_id, []) or [])
        except TypeError:
            return set()

    @staticmethod
    def _file_data_size(file_data: dict[str, Any]) -> int:
        try:
            return len("\n".join(file_data.get("content") or []))
        except Exception:
            return 0

    def _normalize_listing_path(self, path: str) -> str:
        if not path:
            return DOCUMENTS_ROOT
        if path == "/":
            return path
        return path.rstrip("/") if path != "/" else path

    def _moved_view_paths(
        self,
        existing: dict[str, dict[str, Any]],
    ) -> tuple[set[str], dict[str, str]]:
        """Apply ``pending_moves`` to a path set and return ``(removed, alias)``.

        Removed paths should disappear from listings; ``alias[source] = dest``
        means a virtual entry should appear at ``dest`` even if no DB row is
        yet there.
        """
        removed: set[str] = set()
        alias: dict[str, str] = {}
        for move in self._pending_moves():
            src = move.get("source")
            dst = move.get("dest")
            if not src or not dst:
                continue
            removed.add(src)
            alias[src] = dst
            existing.pop(src, None)
        return removed, alias

    # ------------------------------------------------------------------ ls/read

    async def als_info(self, path: str) -> list[FileInfo]:  # type: ignore[override]
        normalized = self._normalize_listing_path(path)
        infos: list[FileInfo] = []
        seen: set[str] = set()

        anon = self._kb_anon_doc()
        if anon:
            anon_path = str(anon.get("path") or "")
            if (
                anon_path
                and _is_under(anon_path, normalized)
                and anon_path != normalized
                and anon_path not in seen
            ):
                infos.append(
                    FileInfo(
                        path=anon_path,
                        is_dir=False,
                        size=len(str(anon.get("content") or "")),
                        modified_at="",
                    )
                )
                seen.add(anon_path)

        files = self._state_files()
        moved_removed, moved_alias = self._moved_view_paths(files)

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    db_infos, subdir_paths = await self._list_db_directory(
                        session, normalized
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.als_info DB error: %s", exc)
                db_infos, subdir_paths = [], set()

            for info in db_infos:
                p = info.get("path", "")
                if not p or p in seen or p in moved_removed:
                    continue
                infos.append(info)
                seen.add(p)

            for src, dst in moved_alias.items():
                if src not in seen:
                    if not _is_under(dst, normalized):
                        continue
                    rel = (
                        dst[len(normalized) :].lstrip("/")
                        if normalized != "/"
                        else dst.lstrip("/")
                    )
                    if "/" in rel:
                        subdir_paths.add(
                            (normalized.rstrip("/") + "/" + rel.split("/", 1)[0])
                            if normalized != "/"
                            else "/" + rel.split("/", 1)[0]
                        )
                        continue
                    if dst in seen:
                        continue
                    fd = files.get(dst)
                    size = self._file_data_size(fd) if isinstance(fd, dict) else 0
                    infos.append(
                        FileInfo(
                            path=dst,
                            is_dir=False,
                            size=int(size),
                            modified_at=fd.get("modified_at", "")
                            if isinstance(fd, dict)
                            else "",
                        )
                    )
                    seen.add(dst)

            for staged in self._staged_dirs():
                if not staged or not staged.startswith(DOCUMENTS_ROOT):
                    continue
                if staged == normalized:
                    continue
                if not _is_under(staged, normalized):
                    continue
                rel = (
                    staged[len(normalized) :].lstrip("/")
                    if normalized != "/"
                    else staged.lstrip("/")
                )
                if not rel:
                    continue
                first = rel.split("/", 1)[0]
                immediate = (
                    normalized.rstrip("/") + "/" + first
                    if normalized != "/"
                    else "/" + first
                )
                subdir_paths.add(immediate)

            for sub in sorted(subdir_paths):
                if sub in seen:
                    continue
                infos.append(FileInfo(path=sub, is_dir=True, size=0, modified_at=""))
                seen.add(sub)

        for path_key, fd in files.items():
            if not isinstance(path_key, str) or path_key in seen:
                continue
            if not _is_under(path_key, normalized) or path_key == normalized:
                continue
            if normalized == "/":
                rel = path_key.lstrip("/")
            else:
                rel = path_key[len(normalized) :].lstrip("/")
            if not rel:
                continue
            if "/" in rel:
                first = rel.split("/", 1)[0]
                immediate = (
                    normalized.rstrip("/") + "/" + first
                    if normalized != "/"
                    else "/" + first
                )
                if immediate not in seen:
                    infos.append(
                        FileInfo(path=immediate, is_dir=True, size=0, modified_at="")
                    )
                    seen.add(immediate)
                continue
            include = path_key.startswith(DOCUMENTS_ROOT) or _basename(
                path_key
            ).startswith(_TEMP_PREFIX)
            if not include:
                continue
            size = self._file_data_size(fd) if isinstance(fd, dict) else 0
            infos.append(
                FileInfo(
                    path=path_key,
                    is_dir=False,
                    size=int(size),
                    modified_at=fd.get("modified_at", "")
                    if isinstance(fd, dict)
                    else "",
                )
            )
            seen.add(path_key)

        infos.sort(key=lambda fi: (not fi.get("is_dir", False), fi.get("path", "")))
        return infos

    def ls_info(self, path: str) -> list[FileInfo]:  # type: ignore[override]
        return asyncio.run(self.als_info(path))

    async def _list_db_directory(
        self,
        session: AsyncSession,
        normalized_path: str,
    ) -> tuple[list[FileInfo], set[str]]:
        """List immediate Folders + Documents at ``normalized_path``.

        Returns ``(file_infos, subdirectory_paths)``. ``normalized_path`` may
        be ``/`` (synthesizes ``/documents``) or a path under ``/documents``.
        """
        if normalized_path == "/":
            return (
                [],
                {DOCUMENTS_ROOT},
            )

        if not normalized_path.startswith(DOCUMENTS_ROOT):
            return [], set()

        index = await build_path_index(session, self.search_space_id)
        target_folder_id: int | None = None
        if normalized_path != DOCUMENTS_ROOT:
            target_path = normalized_path
            matches = [
                fid for fid, fpath in index.folder_paths.items() if fpath == target_path
            ]
            if not matches:
                return [], set()
            target_folder_id = matches[0]

        result = await session.execute(
            select(Document.id, Document.title, Document.folder_id, Document.updated_at)
            .where(Document.search_space_id == self.search_space_id)
            .where(
                Document.folder_id == target_folder_id
                if target_folder_id is not None
                else Document.folder_id.is_(None)
            )
        )
        rows = result.all()

        file_infos: list[FileInfo] = []
        for row in rows:
            path = doc_to_virtual_path(
                doc_id=row.id,
                title=str(row.title or "untitled"),
                folder_id=row.folder_id,
                index=index,
            )
            modified = ""
            if row.updated_at is not None:
                with contextlib.suppress(Exception):
                    modified = row.updated_at.astimezone(UTC).isoformat()
            file_infos.append(
                FileInfo(
                    path=path,
                    is_dir=False,
                    size=0,
                    modified_at=modified,
                )
            )

        subdirs: set[str] = set()
        for _fid, fpath in index.folder_paths.items():
            if fpath == normalized_path:
                continue
            base = normalized_path.rstrip("/")
            if not fpath.startswith(base + "/"):
                continue
            rel = fpath[len(base) + 1 :]
            if "/" in rel:
                continue
            subdirs.add(base + "/" + rel)
        return file_infos, subdirs

    async def aread(  # type: ignore[override]
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str:
        files = self._state_files()
        file_data = files.get(file_path)
        if file_data is not None:
            return format_read_response(file_data, offset, limit)

        loaded = await self._load_file_data(file_path)
        if loaded is None:
            return f"Error: File '{file_path}' not found"
        file_data, _ = loaded
        return format_read_response(file_data, offset, limit)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:  # type: ignore[override]
        return asyncio.run(self.aread(file_path, offset, limit))

    async def _load_file_data(
        self,
        path: str,
    ) -> tuple[dict[str, Any], int | None] | None:
        """Lazy-load a virtual KB document into a deepagents ``FileData``.

        Returns ``(file_data, doc_id)`` or ``None`` if the path doesn't map
        to any known document. ``doc_id`` is ``None`` for the synthetic
        anonymous document so the caller doesn't track it as a DB-backed file.
        """
        anon = self._kb_anon_doc()
        if anon and str(anon.get("path") or "") == path:
            doc_payload = {
                "document_id": -1,
                "chunks": list(anon.get("chunks") or []),
                "matched_chunk_ids": [],
                "document": {
                    "id": -1,
                    "title": anon.get("title") or "uploaded_document",
                    "document_type": "FILE",
                    "metadata": {"source": "anonymous_upload"},
                },
                "source": "FILE",
            }
            xml = build_document_xml(doc_payload, matched_chunk_ids=set())
            file_data = create_file_data(xml)
            return file_data, None

        if not path.startswith(DOCUMENTS_ROOT):
            return None

        async with shielded_async_session() as session:
            document = await virtual_path_to_doc(
                session,
                search_space_id=self.search_space_id,
                virtual_path=path,
            )
            if document is None:
                return None
            chunk_rows = await session.execute(
                select(Chunk.id, Chunk.content)
                .where(Chunk.document_id == document.id)
                .order_by(Chunk.id)
            )
            chunks = [
                {"chunk_id": row.id, "content": row.content} for row in chunk_rows.all()
            ]

        doc_payload = {
            "document_id": document.id,
            "chunks": chunks,
            "matched_chunk_ids": list(self._matched_chunk_ids(document.id)),
            "document": {
                "id": document.id,
                "title": document.title,
                "document_type": (
                    document.document_type.value
                    if getattr(document, "document_type", None) is not None
                    else "UNKNOWN"
                ),
                "metadata": dict(document.document_metadata or {}),
            },
            "source": (
                document.document_type.value
                if getattr(document, "document_type", None) is not None
                else "UNKNOWN"
            ),
        }
        xml = build_document_xml(
            doc_payload,
            matched_chunk_ids=self._matched_chunk_ids(document.id),
        )
        file_data = create_file_data(xml)
        return file_data, document.id

    # ------------------------------------------------------------------ writes

    async def awrite(self, file_path: str, content: str) -> WriteResult:  # type: ignore[override]
        files = self._state_files()
        if file_path in files:
            return WriteResult(
                error=(
                    f"Cannot write to {file_path} because it already exists. "
                    "Read and then make an edit, or write to a new path."
                )
            )
        new_file_data = create_file_data(content)
        return WriteResult(path=file_path, files_update={file_path: new_file_data})

    def write(self, file_path: str, content: str) -> WriteResult:  # type: ignore[override]
        return asyncio.run(self.awrite(file_path, content))

    async def aedit(  # type: ignore[override]
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        files = self._state_files()
        file_data = files.get(file_path)
        if file_data is None:
            loaded = await self._load_file_data(file_path)
            if loaded is None:
                return EditResult(error=f"Error: File '{file_path}' not found")
            file_data, _ = loaded

        content = file_data_to_string(file_data)
        result = perform_string_replacement(
            content, old_string, new_string, replace_all
        )
        if isinstance(result, str):
            return EditResult(error=result)

        new_content, occurrences = result
        new_file_data = update_file_data(file_data, new_content)
        return EditResult(
            path=file_path,
            files_update={file_path: new_file_data},
            occurrences=int(occurrences),
        )

    def edit(  # type: ignore[override]
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return asyncio.run(self.aedit(file_path, old_string, new_string, replace_all))

    # ------------------------------------------------------------------ glob/grep

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:  # type: ignore[override]
        normalized = self._normalize_listing_path(path)
        results: list[FileInfo] = []
        seen: set[str] = set()

        files = self._state_files()
        moved_removed, _ = self._moved_view_paths(files)
        regex = re.compile(fnmatch.translate(pattern))
        for path_key, fd in files.items():
            if path_key in moved_removed:
                continue
            if not _is_under(path_key, normalized):
                continue
            rel = (
                path_key[len(normalized) :].lstrip("/")
                if normalized != "/"
                else path_key.lstrip("/")
            )
            if not regex.match(rel) and not regex.match(path_key):
                continue
            if path_key in seen:
                continue
            size = self._file_data_size(fd) if isinstance(fd, dict) else 0
            results.append(
                FileInfo(
                    path=path_key,
                    is_dir=False,
                    size=int(size),
                    modified_at=fd.get("modified_at", "")
                    if isinstance(fd, dict)
                    else "",
                )
            )
            seen.add(path_key)

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    index = await build_path_index(session, self.search_space_id)
                    rows = await session.execute(
                        select(Document.id, Document.title, Document.folder_id).where(
                            Document.search_space_id == self.search_space_id
                        )
                    )
                    for row in rows.all():
                        candidate = doc_to_virtual_path(
                            doc_id=row.id,
                            title=str(row.title or "untitled"),
                            folder_id=row.folder_id,
                            index=index,
                        )
                        if candidate in seen or candidate in moved_removed:
                            continue
                        if not _is_under(candidate, normalized):
                            continue
                        rel = (
                            candidate[len(normalized) :].lstrip("/")
                            if normalized != "/"
                            else candidate.lstrip("/")
                        )
                        if not regex.match(rel) and not regex.match(candidate):
                            continue
                        results.append(
                            FileInfo(
                                path=candidate, is_dir=False, size=0, modified_at=""
                            )
                        )
                        seen.add(candidate)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.aglob_info DB error: %s", exc)

        results.sort(key=lambda fi: fi.get("path", ""))
        return results

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:  # type: ignore[override]
        return asyncio.run(self.aglob_info(pattern, path))

    async def agrep_raw(  # type: ignore[override]
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        if not pattern:
            return "Error: pattern cannot be empty"

        normalized = self._normalize_listing_path(path or "/")
        matches: list[GrepMatch] = []

        files = self._state_files()
        moved_removed, _ = self._moved_view_paths(files)
        glob_re = re.compile(fnmatch.translate(glob)) if glob else None
        for path_key, fd in files.items():
            if path_key in moved_removed:
                continue
            if not _is_under(path_key, normalized):
                continue
            if glob_re is not None and not glob_re.match(_basename(path_key)):
                continue
            if not isinstance(fd, dict):
                continue
            for line_no, line in enumerate(fd.get("content") or [], 1):
                if pattern in line:
                    matches.append(
                        GrepMatch(path=path_key, line=int(line_no), text=str(line))
                    )
                    if len(matches) >= _GREP_MAX_TOTAL_MATCHES:
                        return matches

        if normalized.startswith(DOCUMENTS_ROOT) or normalized == "/":
            try:
                async with shielded_async_session() as session:
                    index = await build_path_index(session, self.search_space_id)
                    sub = (
                        select(Chunk.document_id, Chunk.id, Chunk.content)
                        .join(Document, Document.id == Chunk.document_id)
                        .where(Document.search_space_id == self.search_space_id)
                        .where(Chunk.content.ilike(f"%{pattern}%"))
                        .order_by(Chunk.document_id, Chunk.id)
                    )
                    chunk_rows = await session.execute(sub)
                    per_doc: dict[int, int] = {}
                    doc_id_to_path: dict[int, str] = {}
                    needed_doc_ids: set[int] = set()
                    chunk_buffer: list[tuple[int, int, str]] = []
                    for row in chunk_rows.all():
                        per_doc.setdefault(row.document_id, 0)
                        if per_doc[row.document_id] >= _GREP_MAX_PER_DOC:
                            continue
                        per_doc[row.document_id] += 1
                        chunk_buffer.append((row.document_id, row.id, row.content))
                        needed_doc_ids.add(row.document_id)
                        if sum(per_doc.values()) >= _GREP_MAX_TOTAL_MATCHES - len(
                            matches
                        ):
                            break
                    if needed_doc_ids:
                        doc_rows = await session.execute(
                            select(
                                Document.id, Document.title, Document.folder_id
                            ).where(Document.id.in_(list(needed_doc_ids)))
                        )
                        for row in doc_rows.all():
                            doc_id_to_path[row.id] = doc_to_virtual_path(
                                doc_id=row.id,
                                title=str(row.title or "untitled"),
                                folder_id=row.folder_id,
                                index=index,
                            )
                    for doc_id, chunk_id, content in chunk_buffer:
                        candidate = doc_id_to_path.get(doc_id)
                        if not candidate or candidate in moved_removed:
                            continue
                        if not _is_under(candidate, normalized):
                            continue
                        if glob_re is not None and not glob_re.match(
                            _basename(candidate)
                        ):
                            continue
                        snippet = " ".join(str(content).split())[:240]
                        matches.append(
                            GrepMatch(
                                path=candidate,
                                line=0,
                                text=(
                                    f"<chunk-match in {candidate} chunk_id={chunk_id}>: "
                                    f"{snippet}"
                                ),
                            )
                        )
                        if len(matches) >= _GREP_MAX_TOTAL_MATCHES:
                            break
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("KBPostgresBackend.agrep_raw DB error: %s", exc)

        return matches

    def grep_raw(  # type: ignore[override]
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        return asyncio.run(self.agrep_raw(pattern, path, glob))

    # ------------------------------------------------------------------ list_tree (helper)

    async def alist_tree_listing(
        self,
        path: str = DOCUMENTS_ROOT,
        *,
        max_depth: int | None = 8,
        page_size: int = 500,
        include_files: bool = True,
        include_dirs: bool = True,
    ) -> dict[str, Any]:
        """Recursive tree listing for cloud mode.

        Mirrors the shape returned by :class:`MultiRootLocalFolderBackend.list_tree`:
        ``{"entries": [{path, is_dir, size, modified_at, depth}, ...], "truncated": bool}``.
        """
        normalized = self._normalize_listing_path(path or DOCUMENTS_ROOT)
        if not normalized.startswith(DOCUMENTS_ROOT) and normalized != "/":
            return {"error": "Error: path must be under /documents/"}

        entries: list[dict[str, Any]] = []
        truncated = False

        try:
            async with shielded_async_session() as session:
                index = await build_path_index(session, self.search_space_id)
                doc_rows_raw = await session.execute(
                    select(
                        Document.id,
                        Document.title,
                        Document.folder_id,
                        Document.updated_at,
                    ).where(Document.search_space_id == self.search_space_id)
                )
                doc_rows = list(doc_rows_raw.all())
        except Exception as exc:  # pragma: no cover
            logger.warning("KBPostgresBackend.alist_tree_listing DB error: %s", exc)
            return {"entries": [], "truncated": False}

        files = self._state_files()
        moved_removed, _ = self._moved_view_paths(files)
        anon = self._kb_anon_doc()
        anon_path = str(anon.get("path") or "") if anon else ""

        def _depth_of(p: str) -> int:
            if p == DOCUMENTS_ROOT:
                return 0
            rel_root = (
                p[len(DOCUMENTS_ROOT) :].lstrip("/")
                if normalized.startswith(DOCUMENTS_ROOT)
                else p.lstrip("/")
            )
            return len([part for part in rel_root.split("/") if part])

        def _add_entry(entry: dict[str, Any]) -> bool:
            nonlocal truncated
            if len(entries) >= page_size:
                truncated = True
                return False
            entries.append(entry)
            return True

        if include_dirs:
            for _fid, fpath in sorted(index.folder_paths.items(), key=lambda kv: kv[1]):
                if not _is_under(fpath, normalized):
                    continue
                depth = _depth_of(fpath)
                if max_depth is not None and depth > max_depth:
                    continue
                if not _add_entry(
                    {
                        "path": fpath,
                        "is_dir": True,
                        "size": 0,
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}
            for staged in self._staged_dirs():
                if not _is_under(staged, normalized):
                    continue
                depth = _depth_of(staged)
                if max_depth is not None and depth > max_depth:
                    continue
                if any(e["path"] == staged for e in entries):
                    continue
                if not _add_entry(
                    {
                        "path": staged,
                        "is_dir": True,
                        "size": 0,
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

        if include_files:
            for row in sorted(doc_rows, key=lambda r: str(r.title or "")):
                candidate = doc_to_virtual_path(
                    doc_id=row.id,
                    title=str(row.title or "untitled"),
                    folder_id=row.folder_id,
                    index=index,
                )
                if candidate in moved_removed:
                    continue
                if not _is_under(candidate, normalized):
                    continue
                depth = _depth_of(candidate)
                if max_depth is not None and depth > max_depth:
                    continue
                modified = ""
                if row.updated_at is not None:
                    with contextlib.suppress(Exception):
                        modified = row.updated_at.astimezone(UTC).isoformat()
                if not _add_entry(
                    {
                        "path": candidate,
                        "is_dir": False,
                        "size": 0,
                        "modified_at": modified,
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

            if anon_path and _is_under(anon_path, normalized):
                depth = _depth_of(anon_path)
                if (max_depth is None or depth <= max_depth) and not _add_entry(
                    {
                        "path": anon_path,
                        "is_dir": False,
                        "size": len(str(anon.get("content") or "")),
                        "modified_at": "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

            for path_key, fd in files.items():
                if not isinstance(path_key, str):
                    continue
                if not _is_under(path_key, normalized):
                    continue
                if any(e["path"] == path_key for e in entries):
                    continue
                if not (
                    path_key.startswith(DOCUMENTS_ROOT)
                    or _basename(path_key).startswith(_TEMP_PREFIX)
                ):
                    continue
                depth = _depth_of(path_key)
                if max_depth is not None and depth > max_depth:
                    continue
                size = self._file_data_size(fd) if isinstance(fd, dict) else 0
                if not _add_entry(
                    {
                        "path": path_key,
                        "is_dir": False,
                        "size": int(size),
                        "modified_at": fd.get("modified_at", "")
                        if isinstance(fd, dict)
                        else "",
                        "depth": depth,
                    }
                ):
                    return {"entries": entries, "truncated": True}

        return {"entries": entries, "truncated": truncated}

    # ------------------------------------------------------------------ uploads (unsupported)

    def upload_files(  # type: ignore[override]
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        msg = "KBPostgresBackend does not support upload_files."
        raise NotImplementedError(msg)

    def download_files(  # type: ignore[override]
        self, paths: list[str]
    ) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        files = self._state_files()
        for path in paths:
            fd = files.get(path)
            if fd is None:
                responses.append(
                    FileDownloadResponse(
                        path=path, content=None, error="file_not_found"
                    )
                )
                continue
            content_str = file_data_to_string(fd)
            responses.append(
                FileDownloadResponse(
                    path=path,
                    content=content_str.encode("utf-8"),
                    error=None,
                )
            )
        return responses


# --- module-level small helpers ---------------------------------------------


async def list_tree_listing(
    backend: KBPostgresBackend,
    path: str,
    *,
    max_depth: int | None = 8,
    page_size: int = 500,
    include_files: bool = True,
    include_dirs: bool = True,
) -> dict[str, Any]:
    """Async helper used by the overridden ``list_tree`` tool wrapper."""
    return await backend.alist_tree_listing(
        path,
        max_depth=max_depth,
        page_size=page_size,
        include_files=include_files,
        include_dirs=include_dirs,
    )


__all__ = [
    "KBPostgresBackend",
    "list_tree_listing",
    "paginate_listing",
]
