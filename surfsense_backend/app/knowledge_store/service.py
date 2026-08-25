"""The knowledge store facade: one door for every reader and writer.

Agent turns, editor saves, uploads, connector syncs, deletes and moves all go
through :class:`KnowledgeStore`. It binds a workspace to its engine, opens the
one place a revision is recorded, and projects the rows the UI reads. Driven
consumers (the indexer) read revisions and changes off it and leave rows to the
projection.

A writer names its actor and its session with the builder before acting::

    store = (
        KnowledgeStore.for_workspace(workspace_id)
        .with_session(session)
        .as_user(user_id)
    )
    outcome = await store.save_document(document, markdown)

Every write returns an :class:`Outcome`. Writes never raise while the Postgres
path still coexists with the store: a store that cannot be reached must not fail
a mutation the user already made, so failures are logged and counted and the
drift sweep is what notices.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from app.knowledge_store.engines.base import VersionedContentEngine
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.factory import build_engine
from app.knowledge_store.identities import AGENT_IDENTITY, user_identity
from app.knowledge_store.locks import workspace_write_lock
from app.knowledge_store.paths import (
    StorePathError,
    recorded_virtual_path,
    workspace_store_path,
    workspace_working_copies_path,
)
from app.knowledge_store.schemas import (
    Change,
    Outcome,
    Revision,
    TrackedPath,
    WorkingCopy,
)
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)
from app.knowledge_store.transaction import Transaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import Document, Folder
    from app.knowledge_store.remote.facade import WorkspaceRemotes

logger = logging.getLogger(__name__)


class KnowledgeStore:
    """Versioned content for one workspace, and the verbs that change it."""

    def __init__(
        self,
        workspace_id: int | str,
        engine: VersionedContentEngine,
        *,
        session: AsyncSession | None = None,
        author_user_id: str | None = None,
        committer: str | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._engine = engine
        self._session = session
        self._author_user_id = author_user_id
        self._committer = committer

    # ----------------------------------------------------------------- builder

    @classmethod
    def for_workspace(cls, workspace_id: int | str) -> KnowledgeStore:
        """Bind a workspace to its engine; the only place that binding happens."""
        return cls(workspace_id, build_engine(workspace_id))

    def with_session(self, session: AsyncSession) -> KnowledgeStore:
        """Bind the DB session the row-touching capabilities read and write."""
        return self._rebind(session=session)

    def as_user(self, user_id: str | None) -> KnowledgeStore:
        """Attribute writes to a user (or to the agent when ``user_id`` is None)."""
        return self._rebind(author_user_id=user_id, committer=None)

    def as_agent(self, *, on_behalf_of: str | None = None) -> KnowledgeStore:
        """Record as the agent on behalf of a user: user authors, agent commits."""
        return self._rebind(author_user_id=on_behalf_of, committer=AGENT_IDENTITY)

    def _rebind(self, **overrides) -> KnowledgeStore:
        fields = {
            "session": self._session,
            "author_user_id": self._author_user_id,
            "committer": self._committer,
            **overrides,
        }
        return KnowledgeStore(self._workspace_id, self._engine, **fields)

    @property
    def workspace_id(self) -> int | str:
        return self._workspace_id

    # ------------------------------------------------------------------- reads

    async def read_as_of(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of ``revision``."""
        return await asyncio.to_thread(self._engine.read_as_of, revision, path)

    async def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        """Revisions newest-first, optionally scoped to a single ``path``."""
        return await asyncio.to_thread(
            self._engine.list_revisions, path=path, limit=limit
        )

    async def list_changes(
        self, revision: str, *, since: str | None = None
    ) -> list[Change]:
        """What ``revision`` changed, against its parent or against ``since``."""
        return await asyncio.to_thread(self._engine.list_changes, revision, since=since)

    async def list_paths(self, revision: str) -> list[TrackedPath]:
        """Every path stored at ``revision``, with its content address."""
        return await asyncio.to_thread(self._engine.list_paths, revision)

    async def head(self) -> str | None:
        """Id of the workspace's current revision, or ``None`` when empty."""
        return await asyncio.to_thread(self._engine.get_current_revision)

    #: Name driven consumers know the head read by; :meth:`head` is the verb.
    get_current_revision = head

    def compute_content_id(self, data: bytes) -> str:
        """Content address for ``data`` (no I/O)."""
        return self._engine.compute_content_id(data)

    @property
    def remotes(self) -> WorkspaceRemotes:
        """Git remotes attached to this workspace."""
        from app.knowledge_store.remote.facade import WorkspaceRemotes

        return WorkspaceRemotes(
            self._workspace_id,
            cast(GitContentEngine, self._engine),
            self._require_session(),
        )

    async def push(
        self, *, url: str, ref: str, username: str, password: str
    ) -> str:
        """Fast-forward HEAD to ``url`` at ``ref``. Thread hop onto the engine."""
        engine = cast(GitContentEngine, self._engine)
        return await asyncio.to_thread(
            lambda: engine.push(
                url=url, ref=ref, username=username, password=password
            )
        )

    def _enqueue_after_revision(self) -> None:
        from app.knowledge_store.index.queue import enqueue_index
        from app.knowledge_store.remote.queue import enqueue_push

        enqueue_index(self._workspace_id)
        enqueue_push(self._workspace_id)

    # --------------------------------------------------------- working copies

    async def open_working_copy(self, copy_id: str) -> WorkingCopy:
        """Private on-disk copy of the current content; reopens an existing one."""
        return await asyncio.to_thread(self._engine.open_working_copy, copy_id)

    async def diff_working_copy(
        self, copy_id: str
    ) -> tuple[dict[str, bytes], list[str]]:
        """Net changes in ``copy_id`` since its base, as ``(writes, removes)``."""
        return await asyncio.to_thread(self._engine.diff_working_copy, copy_id)

    async def discard_working_copy(self, copy_id: str) -> None:
        """Delete ``copy_id``'s working copy; a no-op if absent."""
        await asyncio.to_thread(self._engine.discard_working_copy, copy_id)

    async def prune_working_copies(self, *, older_than_seconds: float) -> list[str]:
        """Delete abandoned working copies; returns the pruned ids."""
        return await asyncio.to_thread(
            lambda: self._engine.prune_working_copies(
                older_than_seconds=older_than_seconds
            )
        )

    # -------------------------------------------------------- write primitives

    @asynccontextmanager
    async def transaction(
        self, *, message: str, author: str, committer: str | None = None
    ):
        """The one unit of work: verbs staged in the scope become one revision.

        ``author`` is whose content change this is; ``committer`` (default
        ``author``) is who recorded it — the agent identity for agent turns. The
        revision is recorded under the write lock on clean exit, nothing on an
        exception. The facade is the only caller; consumers reach it through
        :meth:`revise` or a capability.
        """
        tx = Transaction()
        yield tx
        async with workspace_write_lock(self._workspace_id):
            tx.revision = await asyncio.to_thread(
                self._record, tx, message, author, committer
            )

    @asynccontextmanager
    async def revise(self, *, message: str):
        """Batch several verbs into one revision, attributed to the bound actor."""
        async with self.transaction(
            message=message,
            author=user_identity(self._author_user_id),
            committer=self._committer,
        ) as tx:
            yield tx

    async def write(self, path: str, content: str | bytes) -> Outcome:
        """Create or replace one path as a single-verb revision."""
        data = content.encode() if isinstance(content, str) else content
        return await self._single(
            lambda tx: tx.write(path, data), f"docs: write {_leaf(path)}"
        )

    async def remove(self, path: str) -> Outcome:
        """Delete one path as a single-verb revision."""
        return await self._single(
            lambda tx: tx.remove(path), f"docs: delete {_leaf(path)}"
        )

    async def move(self, source: str, destination: str) -> Outcome:
        """Relocate one path as a single-verb revision."""
        return await self._single(
            lambda tx: tx.move(source, destination),
            f"docs: move {_leaf(destination)}",
        )

    async def _single(self, stage, message: str) -> Outcome:
        async with self.revise(message=message) as tx:
            stage(tx)
        return await self._outcome(tx.revision)

    def _record(
        self, tx: Transaction, message: str, author: str, committer: str | None
    ) -> str | None:
        writes, removes = tx.resolve(self._engine.read)
        return self._engine.record(
            writes=writes,
            removes=removes,
            message=message,
            author=author,
            committer=committer,
        )

    async def _outcome(self, revision: str | None) -> Outcome:
        if revision is None:
            return Outcome(revision=None)
        return Outcome(revision=revision, changes=await self.list_changes(revision))

    async def _commit_files(
        self,
        *,
        files: Mapping[str, str],
        message: str,
        removes: Sequence[str] = (),
        moves: Sequence[tuple[str, str]] = (),
    ) -> str | None:
        """Record markdown writes, removes and moves as one revision, then enqueue.

        ``None`` when the store is disabled, the batch is empty, or the content
        was unchanged. Enqueues the derived index and a remote push only once
        the revision is durable, so a broker outage degrades to the sweep.
        """
        if (not files and not removes and not moves) or not (
            load_knowledge_store_settings().enabled
        ):
            return None
        async with self.revise(message=message) as tx:
            for path, markdown in files.items():
                tx.write(path, markdown.encode())
            for path in removes:
                tx.remove(path)
            for source, destination in moves:
                tx.move(source, destination)
        if tx.revision is not None:
            self._enqueue_after_revision()
        return tx.revision

    async def _taken_virtual_paths(
        self, *, exclude: set[str] | None = None
    ) -> set[str]:
        """The document paths git already holds, so a fresh name skips them.

        Occupancy comes from the tree, the one authority on which files exist;
        ``.keep`` markers are folders, not names to dodge. ``exclude`` drops the
        caller's own current path so a retitle to the same name is not read as a
        collision with itself. `ponytail:` walks the whole tree per authored
        write — fine at today's sizes, cache by revision if a workspace grows.
        """
        from app.knowledge_store.paths import KEEP_FILE, to_virtual_path

        head = await self.head()
        if head is None:
            return set()
        skip = exclude or set()
        taken: set[str] = set()
        for entry in await self.list_paths(head):
            if entry.path.rsplit("/", 1)[-1] == KEEP_FILE:
                continue
            virtual = to_virtual_path(entry.path)
            if virtual not in skip:
                taken.add(virtual)
        return taken

    def _folder_parts(self, folder_id: int | None, index) -> tuple[str, ...]:
        from app.knowledge_store.paths import DOCUMENTS_ROOT

        base = index.folder_paths.get(folder_id, DOCUMENTS_ROOT)
        relative = base[len(DOCUMENTS_ROOT) :].strip("/")
        return tuple(relative.split("/")) if relative else ()

    def _author_path(
        self, *, title: str, folder_id: int | None, index, taken: set[str]
    ) -> str:
        """A fresh ``.md`` path under the row's folder, breaking a name clash.

        The naming law, not the legacy ``.xml`` derivation: this is the one place
        a live write chooses a name, so it is the one place the spelling is fixed.
        """
        from app.knowledge_store.paths import allocate_path

        return allocate_path(
            name=str(title or "untitled"),
            folder_parts=self._folder_parts(folder_id, index),
            taken=taken,
        ).virtual_path

    async def _reattach_or_author_path(
        self,
        doc: Document | None,
        *,
        title: str,
        folder_id: int | None,
        index,
        taken: set[str],
    ) -> str:
        """Place a document that records no path: re-attach its file, else author.

        The one such decision the live writers (a save and a sync ingest) share:
        re-attach to the doc's own stranded file when git already holds the
        canonical name and the row still resolves back to this doc, and only then
        author a fresh name. Without the re-attach a lost recorded path — the
        crash window between the commit and the write-back, or a legacy row that
        never had one — forks the file into ``name (2)``. A row loaded as ``None``
        (a save whose row was deleted underfoot) has no identity to re-attach by,
        so it authors.
        """
        from app.knowledge_store.paths import allocate_path
        from app.knowledge_store.paths.resolve import virtual_path_to_doc

        canonical = allocate_path(
            name=str(title or "untitled"),
            folder_parts=self._folder_parts(folder_id, index),
            taken=set(),
        ).virtual_path
        if doc is not None and canonical in taken:
            existing = await virtual_path_to_doc(
                self._require_session(),
                workspace_id=self._workspace_id,
                virtual_path=canonical,
            )
            if existing is not None and existing.id == doc.id:
                return canonical
        return self._author_path(
            title=title, folder_id=folder_id, index=index, taken=taken
        )

    # ---------------------------------------------------------- capabilities

    async def save_document(
        self,
        *,
        doc_id: int,
        title: str,
        folder_id: int | None,
        markdown: str,
        title_is_explicit: bool = False,
    ) -> Outcome:
        """Record one document's save at its canonical path.

        The path is remembered on the row's ``path`` column so the next save
        knows where the document used to live and can drop that file when a
        retitle moves it. The column is written only once a revision landed: a
        path without a file would look indexer-owned and a rebuild would prune
        it. ``title_is_explicit`` lets an authored title place the file; a title
        re-read from a heading follows the recorded path instead.
        """
        if not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        session = self._require_session()
        from app.db import Document
        from app.knowledge_store.paths import (
            build_path_index,
            to_store_path,
        )
        from app.observability import metrics

        try:
            index = await build_path_index(
                session, self._workspace_id, populate_occupants=False
            )
            document = await session.get(Document, doc_id)
            metadata = document.document_metadata if document else None
            previous = recorded_virtual_path(
                metadata, document.path if document else None
            )
            # A recorded path stays put; only an explicit title, or a first write,
            # authors a new one. Re-deriving a recorded path is the legacy churn.
            if previous is not None and not title_is_explicit:
                virtual_path = previous
            else:
                # The row's own file must not read as a rival, or a re-derivation
                # collides the document with itself.
                taken = await self._taken_virtual_paths(
                    exclude={previous} if previous else set()
                )
                virtual_path = await self._reattach_or_author_path(
                    document,
                    title=title,
                    folder_id=folder_id,
                    index=index,
                    taken=taken,
                )
            stale = _stale_store_path(previous, virtual_path)
            revision = await self._commit_files(
                files={to_store_path(virtual_path): markdown},
                message=f"docs: save {_leaf(virtual_path)}",
                removes=[stale] if stale else (),
            )
            if revision and document is not None and previous != virtual_path:
                document.path = virtual_path
                await session.commit()
        except Exception as exc:
            _record_failure(metrics, "editor_save", exc, self._workspace_id, doc_id)
            return Outcome(revision=None)
        metrics.record_knowledge_store_record_outcome(
            flow="editor_save", status="recorded" if revision else "noop"
        )
        return await self._outcome(revision)

    async def ingest_documents(self, documents: Sequence[Document]) -> Outcome:
        """Record a sync/upload batch's accepted markdown as one revision."""
        if not documents or not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        session = self._require_session()
        from app.knowledge_store.paths import (
            build_path_index,
            to_store_path,
        )
        from app.observability import metrics

        try:
            index = await build_path_index(
                session, self._workspace_id, populate_occupants=False
            )
            taken = await self._taken_virtual_paths()
            files: dict[str, str] = {}
            placed: list[tuple[Document, str]] = []
            for doc in documents:
                if not doc.source_markdown:
                    continue
                # Where the doc's file already lives, the path column first then
                # the legacy marker: a connector re-sync overwrites its own
                # metadata but never the column. Re-authoring a path for a doc
                # that already has a file forks it into a duplicate.
                previous = recorded_virtual_path(doc.document_metadata, doc.path)
                if previous is not None:
                    virtual_path = previous
                else:
                    virtual_path = await self._reattach_or_author_path(
                        doc,
                        title=doc.title,
                        folder_id=doc.folder_id,
                        index=index,
                        taken=taken,
                    )
                files[to_store_path(virtual_path)] = doc.source_markdown
                placed.append((doc, virtual_path))
            revision = await self._commit_files(
                files=files, message=f"sync: index {len(files)} document(s)"
            )
            if revision:
                for doc, virtual_path in placed:
                    doc.path = virtual_path
                await session.commit()
        except Exception as exc:
            _record_failure(metrics, "sync_batch", exc, self._workspace_id)
            return Outcome(revision=None)
        metrics.record_knowledge_store_record_outcome(
            flow="sync_batch", status="recorded" if revision else "noop"
        )
        return await self._outcome(revision)

    async def delete_documents(self, documents: Sequence[Document]) -> Outcome:
        """Drop the files behind ``documents`` in one revision.

        Call before the rows go: a path is read off its row, and a deleted row
        can no longer say where its file was. Recording ahead of the row delete
        is safe only in this direction — if the delete then fails, the indexer's
        convergence drops the row anyway. The other order is the resurrection
        bug this verb exists for: the file outlives the row and the next rebuild
        reads it back as a document nobody asked for.
        """
        if not documents or not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        session = self._require_session()
        from app.knowledge_store.paths import build_path_index
        from app.observability import metrics

        try:
            index = await build_path_index(session, self._workspace_id)
            removes = [
                path
                for path in (_store_path_of(document, index) for document in documents)
                if path is not None
            ]
            revision = await self._commit_files(
                files={}, message=_summary("delete", removes), removes=removes
            )
        except Exception as exc:
            _record_failure(metrics, "delete", exc, self._workspace_id)
            return Outcome(revision=None)
        metrics.record_knowledge_store_record_outcome(
            flow="delete", status="recorded" if revision else "noop"
        )
        return await self._outcome(revision)

    async def move_documents(self, documents: Sequence[Document]) -> Outcome:
        """Move each document's file to the path its row now describes.

        Recorded as a move, not a delete-plus-write, so the document keeps its id:
        the indexer recognises a rename by asking dulwich to detect it, and a
        churning id would take saved citations and version history with it. One
        verb covers a document move, a bulk move, a folder rename and a folder
        move — a folder is only a path prefix, so renaming one moves every
        descendant. Leaves the updated path for the caller's own commit.
        """
        if not documents or not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        session = self._require_session()
        from app.knowledge_store.paths import build_path_index
        from app.observability import metrics

        try:
            index = await build_path_index(
                session, self._workspace_id, populate_occupants=False
            )
            # Drop the movers' own paths so a batch never collides with a name it
            # is itself vacating; a chosen destination is added back as we go.
            own = {
                p
                for d in documents
                if (p := recorded_virtual_path(d.document_metadata, d.path)) is not None
            }
            taken = await self._taken_virtual_paths(exclude=own)
            moves: list[tuple[str, str]] = []
            moved: list[tuple[Document, str]] = []
            for document in documents:
                relocation = _relocation_of(document, index, taken)
                if relocation is None:
                    continue
                source, destination, virtual_path = relocation
                moves.append((source, destination))
                moved.append((document, virtual_path))
            revision = await self._commit_files(
                files={},
                message=_summary("move", [dst for _, dst in moves]),
                moves=moves,
            )
            if revision:
                for document, virtual_path in moved:
                    document.path = virtual_path
        except Exception as exc:
            _record_failure(metrics, "move", exc, self._workspace_id)
            return Outcome(revision=None)
        metrics.record_knowledge_store_record_outcome(
            flow="move", status="recorded" if revision else "noop"
        )
        return await self._outcome(revision)

    # ------------------------------------------------------------------ folders

    async def create_folder(self, path: str) -> Outcome:
        """Materialize an empty folder as its ``.keep`` marker, one revision."""
        if not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        from app.knowledge_store.paths import KEEP_FILE

        revision = await self._commit_files(
            files={f"{self._folder_store_path(path)}/{KEEP_FILE}": ""},
            message=f"docs: new folder {_leaf(path)}",
        )
        await self._reconcile_folders(revision)
        return await self._outcome(revision)

    async def remove_folder(self, path: str) -> Outcome:
        """Remove a folder and everything under it in one revision."""
        if not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        revision = await self._commit_files(
            files={},
            removes=await self._subtree_paths(path),
            message=f"docs: delete folder {_leaf(path)}",
        )
        await self._reconcile_folders(revision)
        return await self._outcome(revision)

    async def remove_folder_markers(self, path: str) -> Outcome:
        """Drop a folder's ``.keep`` markers, leaving its documents in place.

        The delete route hands document rows to the purge task, which clears
        their chunks and blobs before dropping the rows. Removing their files
        here would race that task: the indexer prunes a row the moment its file
        leaves the tree, and the purge would then find nothing left to clean. So
        this touches only the empty-folder markers, which no row hangs off, and
        lets the purge own the documents.
        """
        if not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        from app.knowledge_store.paths import KEEP_FILE

        keeps = [
            p
            for p in await self._subtree_paths(path)
            if p.rsplit("/", 1)[-1] == KEEP_FILE
        ]
        revision = await self._commit_files(
            files={}, removes=keeps, message=f"docs: delete folder {_leaf(path)}"
        )
        await self._reconcile_folders(revision)
        return await self._outcome(revision)

    async def move_folder(self, source: str, destination: str) -> Outcome:
        """Move a folder and every descendant in one revision, ids preserved."""
        if not await knowledge_store_enabled_for(self._workspace_id):
            return Outcome(revision=None)
        src = self._folder_store_path(source)
        dst = self._folder_store_path(destination)
        moves = [
            (p, f"{dst}{p[len(src) :]}") for p in await self._subtree_paths(source)
        ]
        revision = await self._commit_files(
            files={}, moves=moves, message=f"docs: move folder {_leaf(destination)}"
        )
        # Rename the row in place before reconcile, so its id survives the move;
        # reconcile then finds it already at the live chain and leaves it be.
        if revision is not None:
            await self._reparent_folder_row(source, destination)
        await self._reconcile_folders(revision)
        return await self._outcome(revision)

    async def _reparent_folder_row(self, source: str, destination: str) -> None:
        """Move the folder row for ``source`` onto ``destination`` in place."""
        try:
            workspace_id = int(self._workspace_id)
        except (TypeError, ValueError):
            return
        from app.knowledge_store.index.folders import reparent_folder
        from app.knowledge_store.paths import StorePath, safe_folder_segment

        def chain(path: str) -> tuple[str, ...]:
            return tuple(
                safe_folder_segment(s) for s in StorePath.from_virtual(path).segments
            )

        await reparent_folder(
            self._require_session(),
            workspace_id=workspace_id,
            source_chain=chain(source),
            destination_chain=chain(destination),
            author_id=self._author_user_id,
        )

    def _folder_store_path(self, path: str) -> str:
        """Validated, sanitized ``documents/...`` store path for a folder."""
        from app.knowledge_store.paths import StorePath, safe_folder_segment

        folder = StorePath.from_virtual(path)
        segments = "".join(f"/{safe_folder_segment(s)}" for s in folder.segments)
        return f"documents{segments}"

    async def _subtree_paths(self, path: str) -> list[str]:
        """Every stored path under a folder, its ``.keep`` included."""
        prefix = f"{self._folder_store_path(path)}/"
        head = await self.head()
        tracked = await self.list_paths(head) if head else []
        return [t.path for t in tracked if t.path.startswith(prefix)]

    async def _reconcile_folders(self, revision: str | None) -> None:
        """Match the ``folders`` rows to the tree after a folder revision."""
        if revision is None:
            return
        try:
            workspace_id = int(self._workspace_id)
        except (TypeError, ValueError):
            return
        session = self._require_session()
        from app.knowledge_store.index.folders import (
            live_folder_chains,
            reconcile_folders,
        )

        head = await self.head()
        tracked = await self.list_paths(head) if head else []
        await reconcile_folders(
            session,
            workspace_id=workspace_id,
            live=live_folder_chains(t.path for t in tracked),
            author_id=self._author_user_id,
        )
        await session.commit()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "capability needs a session; call .with_session(session) first"
            )
        return self._session

    # -------------------------------------------------------------- agent turn

    async def open_turn_copy(self, thread_id: object | None) -> WorkingCopy:
        """The turn's private working copy, opened on the first file op."""
        return await self.open_working_copy(thread_working_copy_id(thread_id))

    async def commit_turn(
        self,
        *,
        thread_id: object | None,
        author_user_id: str | None,
        describe,
    ) -> Outcome:
        """Record the turn's working copy as one agent revision, then project.

        ``describe`` turns the net ``(writes, removes)`` into a commit message,
        keeping message generation with its caller. An empty diff records nothing
        and discards the copy. A record failure keeps the copy — the thread's
        next turn recovers it — and re-raises for the caller to answer with
        failed receipts. On success the returned :class:`Outcome` carries the
        projection so the caller can announce rows without re-reading them.
        """
        from app.observability import metrics

        copy_id = thread_working_copy_id(thread_id)
        writes, removes = await self.diff_working_copy(copy_id)
        if not writes and not removes:
            await self.discard_working_copy(copy_id)
            return Outcome(revision=None)

        message = await describe(writes, removes)
        try:
            async with self.transaction(
                message=message,
                author=user_identity(author_user_id),
                committer=AGENT_IDENTITY,
            ) as tx:
                for path, content in writes.items():
                    tx.write(path, content)
                for path in removes:
                    tx.remove(path)
        except Exception as exc:
            metrics.record_knowledge_store_record_outcome(
                flow="turn_commit",
                status="failed",
                error_category=metrics.categorize_exception(exc),
            )
            raise

        await self.discard_working_copy(copy_id)
        metrics.record_knowledge_store_record_outcome(
            flow="turn_commit", status="recorded" if tx.revision else "noop"
        )
        if tx.revision is None:
            return Outcome(revision=None)
        projection = await self._project_turn(tx.revision)
        self._enqueue_after_revision()
        return Outcome(
            revision=tx.revision,
            changes=await self.list_changes(tx.revision),
            projection=projection,
        )

    async def _project_turn(self, revision: str):
        """Write the turn's rows now, on the bound session or a shielded one."""
        from app.knowledge_store.index.project import project_revision

        if self._session is not None:
            return await project_revision(self._session, self._workspace_id, revision)
        from app.db import shielded_async_session

        async with shielded_async_session() as session:
            return await project_revision(session, self._workspace_id, revision)

    # --------------------------------------------------------------- lifecycle

    async def drop_workspace(self) -> None:
        """Delete the workspace's store outright: history, working copies and all.

        Not flag-gated: a workspace seeded ahead of its flip has a store too, and
        leaving it behind would hand its id's next owner someone else's documents.
        """
        import shutil

        for path in (
            workspace_store_path(self._workspace_id),
            workspace_working_copies_path(self._workspace_id),
        ):
            try:
                await asyncio.to_thread(shutil.rmtree, path, ignore_errors=False)
            except FileNotFoundError:
                continue
            except Exception:
                logger.warning(
                    "Could not delete knowledge store directory %s",
                    path,
                    exc_info=True,
                )


def thread_working_copy_id(thread_id: object | None) -> str:
    """The one place the thread -> working-copy-id convention lives.

    The agent's file-op backend and its end-of-turn commit must resolve the same
    copy from the same thread: langgraph serializes turns per thread, and the
    commit reads then discards the copy at end of turn.

    Scoped to the turn, not the actor: subagents append ``::task:{id}`` per
    nesting level, so they resolve the root segment and share the parent's copy —
    the only one the commit reads, and one revision per turn.

    ponytail: a copy left by a crashed turn is reused (and committed) by the
    thread's next turn — recovery semantics; abandoned threads are janitored.
    """
    if thread_id is None:
        return "thread-adhoc"
    root = str(thread_id).split("::", 1)[0]
    # A parentless subagent's id is a bare ``task:{id}``, naming no turn.
    if not root or root.startswith("task:"):
        return "thread-adhoc"
    return f"thread-{root}"


def _leaf(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _summary(verb: str, paths: Sequence[str]) -> str:
    """Commit subject, naming the file when the revision touches only one."""
    if len(paths) == 1:
        return f"docs: {verb} {_leaf(paths[0])}"
    return f"docs: {verb} {len(paths)} documents"


def _record_failure(metrics, flow: str, exc: Exception, workspace_id, doc_id=None):
    logger.warning(
        "Knowledge store recording failed (%s) in workspace %s%s",
        flow,
        workspace_id,
        f" for document {doc_id}" if doc_id is not None else "",
        exc_info=True,
    )
    metrics.record_knowledge_store_record_outcome(
        flow=flow, status="failed", error_category=metrics.categorize_exception(exc)
    )


def _store_path_of(document: Document, index) -> str | None:
    """Where a row's file lives, or ``None`` when it is not the store's to touch."""
    from app.knowledge_store.paths import to_store_path, virtual_path_of

    virtual_path = virtual_path_of(
        path=document.path,
        doc_id=document.id,
        title=document.title,
        folder_id=document.folder_id,
        index=index,
    )
    try:
        return to_store_path(virtual_path)
    except StorePathError:
        return None


def _relocation_of(
    document: Document, index, taken: set[str]
) -> tuple[str, str, str] | None:
    """``(from, to, new virtual path)`` for a row that moved, else ``None``.

    Destination follows the row's folder and title through the ``.md`` naming
    law, the same rule a save uses, so a move never forks the spelling. A row
    with no recorded path has no file yet; the next save writes it where the row
    says.
    """
    from app.knowledge_store.paths import (
        DOCUMENTS_ROOT,
        allocate_path,
        to_store_path,
    )

    previous = recorded_virtual_path(document.document_metadata, document.path)
    if previous is None:
        return None
    base = index.folder_paths.get(document.folder_id, DOCUMENTS_ROOT)
    relative = base[len(DOCUMENTS_ROOT) :].strip("/")
    folder_parts = relative.split("/") if relative else ()
    current = allocate_path(
        name=str(document.title or "untitled"),
        folder_parts=folder_parts,
        taken=taken,
    ).virtual_path
    if current == previous:
        return None
    try:
        return to_store_path(previous), to_store_path(current), current
    except StorePathError:
        return None


def _stale_store_path(previous: str | None, current: str) -> str | None:
    """Store path a save is moving away from, if it is moving at all."""
    from app.knowledge_store.paths import to_store_path

    if not previous or previous == current:
        return None
    try:
        return to_store_path(previous)
    except StorePathError:
        # A marker outside the /documents namespace is not ours to drop.
        return None


# --------------------------------------------------------------------------- #
# Module-level verbs for non-agent writers (routes, Celery tasks, services).
# Thin doors onto the facade so no caller binds a workspace or opens a revision.
# --------------------------------------------------------------------------- #


async def record_markdown_files(
    *,
    workspace_id: int | str,
    files: Mapping[str, str],
    message: str,
    author_user_id: str | None,
    removes: Sequence[str] = (),
    moves: Sequence[tuple[str, str]] = (),
) -> str | None:
    """Record store-path markdown writes/removes/moves as one revision."""
    store = KnowledgeStore.for_workspace(workspace_id).as_user(author_user_id)
    return await store._commit_files(
        files=files, message=message, removes=removes, moves=moves
    )


async def record_saved_document(
    session: AsyncSession,
    *,
    workspace_id: int,
    doc_id: int,
    title: str,
    folder_id: int | None,
    markdown: str,
    author_user_id: str | None,
    title_is_explicit: bool = False,
) -> str | None:
    store = (
        KnowledgeStore.for_workspace(workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    outcome = await store.save_document(
        doc_id=doc_id,
        title=title,
        folder_id=folder_id,
        markdown=markdown,
        title_is_explicit=title_is_explicit,
    )
    return outcome.revision


async def record_prepared_documents(
    session: AsyncSession, documents: Sequence[Document]
) -> str | None:
    if not documents:
        return None
    author = (
        str(documents[0].created_by_id)
        if documents[0].created_by_id is not None
        else None
    )
    store = (
        KnowledgeStore.for_workspace(documents[0].workspace_id)
        .with_session(session)
        .as_user(author)
    )
    return (await store.ingest_documents(documents)).revision


async def record_deleted_documents(
    session: AsyncSession,
    documents: Sequence[Document],
    *,
    author_user_id: str | None = None,
) -> str | None:
    if not documents:
        return None
    store = (
        KnowledgeStore.for_workspace(documents[0].workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    return (await store.delete_documents(documents)).revision


async def record_moved_documents(
    session: AsyncSession,
    documents: Sequence[Document],
    *,
    author_user_id: str | None = None,
) -> str | None:
    if not documents:
        return None
    store = (
        KnowledgeStore.for_workspace(documents[0].workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    return (await store.move_documents(documents)).revision


async def folder_virtual_path(session: AsyncSession, folder: Folder) -> str | None:
    """The ``/documents`` path a folder row occupies, or ``None`` if unplaced.

    The one resolver a route reaches for, so a caller never spells a folder path
    itself. Capture it before a rename mutates the row: git still holds the old
    path, and the move needs both ends.
    """
    from app.knowledge_store.paths import build_path_index

    index = await build_path_index(
        session, folder.workspace_id, populate_occupants=False
    )
    return index.folder_paths.get(folder.id)


async def record_created_folder(
    session: AsyncSession,
    folder: Folder,
    *,
    author_user_id: str | None = None,
) -> str | None:
    """Materialize a new empty folder in git so a rebuild keeps it."""
    path = await folder_virtual_path(session, folder)
    if path is None:
        return None
    store = (
        KnowledgeStore.for_workspace(folder.workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    return (await store.create_folder(path)).revision


async def record_moved_folder(
    session: AsyncSession,
    workspace_id: int,
    *,
    source: str,
    destination: str,
    author_user_id: str | None = None,
) -> str | None:
    """Move a folder's git subtree from ``source`` to ``destination``, id kept."""
    store = (
        KnowledgeStore.for_workspace(workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    return (await store.move_folder(source, destination)).revision


async def record_removed_folder(
    session: AsyncSession,
    workspace_id: int,
    *,
    path: str,
    author_user_id: str | None = None,
) -> str | None:
    """Drop a deleted folder's ``.keep`` markers so an empty folder stays gone."""
    store = (
        KnowledgeStore.for_workspace(workspace_id)
        .with_session(session)
        .as_user(author_user_id)
    )
    return (await store.remove_folder_markers(path)).revision


async def drop_workspace_store(workspace_id: int | str) -> None:
    await KnowledgeStore.for_workspace(workspace_id).drop_workspace()
