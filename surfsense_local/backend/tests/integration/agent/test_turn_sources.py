"""An agent turn's sources resolve as a chat's do, with no opencode needed."""

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent.agent_threads.turn_sources import turn_sources
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.source_roots.managed_root import ensure_managed_root
from modules.source_scope.schemas import SourceScope
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


def test_a_scope_past_a_thousand_sources_bounds_the_turn_whole(engine: Engine) -> None:
    """The client cannot list that many ids; the resolved scope must still hold every one."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Big")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        notes = [
            Document(
                workspace_id=workspace.id,
                title=f"n{n}",
                document_type=DocumentType.NOTE,
                content="x",
                status=DocumentStatus.READY,
                folder_id=library.id,
            )
            for n in range(1003)
        ]
        session.add_all(notes)
        thread = ChatThread(workspace_id=workspace.id, opencode_session_id="ses_1")
        session.add(thread)
        session.flush()
        unticked = notes[0].id
        scope = SourceScope(all=True, excluded_document_ids=[unticked])

        sources = turn_sources(
            session, thread, MessageCreate(text="hi", source_scope=scope)
        )

        assert sources.document_ids is not None
        assert len(sources.document_ids) == 1002
        assert unticked not in sources.document_ids
        assert sources.note is not None and "1002 sources" in sources.note
        # Past the tag's cap the note and the line count them instead.
        assert sources.note.startswith("[surfsense-scope: count=1002]")
        assert sources.shown == {"document_ids": [], "titles": [], "count": 1002}
        assert thread.source_scope["excluded_document_ids"] == [unticked]


def test_a_ticked_folder_still_being_read_is_not_called_nothing_selected(
    engine: Engine,
) -> None:
    """The user did tick sources: the agent is told they are not ready yet."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Reading")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        session.add_all(
            Document(
                workspace_id=workspace.id,
                title=f"scan{n}",
                document_type=DocumentType.FILE,
                status=DocumentStatus.PENDING,
                folder_id=library.id,
            )
            for n in range(2)
        )
        thread = ChatThread(workspace_id=workspace.id, opencode_session_id="ses_1")
        session.add(thread)
        session.flush()
        scope = SourceScope(folder_ids=[library.id])

        sources = turn_sources(
            session, thread, MessageCreate(text="hi", source_scope=scope)
        )

        assert sources.document_ids == []
        assert sources.note is not None
        assert sources.note.startswith("[surfsense-scope: none]")
        assert "No sources are selected" not in sources.note
        assert "2 selected sources are still being read" in sources.note


def _workspace_with_library(session: Session) -> tuple[int, int]:
    workspace = Workspace(name="Research")
    session.add(workspace)
    session.flush()
    return workspace.id, ensure_managed_root(session, workspace.id).id


def _ready(
    session: Session,
    workspace_id: int,
    title: str,
    folder_id: int | None,
    kind: DocumentType = DocumentType.NOTE,
) -> int:
    document = Document(
        workspace_id=workspace_id,
        title=title,
        document_type=kind,
        content="x",
        status=DocumentStatus.READY,
        folder_id=folder_id,
    )
    session.add(document)
    session.flush()
    return document.id


def _agent_thread(session: Session, workspace_id: int) -> ChatThread:
    thread = ChatThread(workspace_id=workspace_id, opencode_session_id="ses_1")
    session.add(thread)
    session.flush()
    return thread


def test_a_turn_on_every_source_sends_no_note_and_takes_filed_artifacts(
    engine: Engine,
) -> None:
    """Every source is the whole Library, a filed Studio artifact too, never an unfiled one."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        note = _ready(session, workspace_id, "Plan", library)
        filed = _ready(session, workspace_id, "Quiz", library, DocumentType.ARTIFACT)
        _ready(session, workspace_id, "Draft", None, DocumentType.ARTIFACT)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(session, thread, MessageCreate(text="hi"))

        assert sources.document_ids == [note, filed]
        assert (sources.note, sources.shown) == (None, None)


def test_ids_sent_alone_are_stored_as_the_threads_scope(engine: Engine) -> None:
    """The tools read the stored scope on each call, so the ids must be stored."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        ticked = _ready(session, workspace_id, "Plan", library)
        _ready(session, workspace_id, "Memo", library)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session, thread, MessageCreate(text="hi", document_ids=[ticked])
        )

        assert sources.document_ids == [ticked]
        assert thread.source_scope["document_ids"] == [ticked]
        assert sources.shown == {"document_ids": [ticked], "titles": ["Plan"]}


def test_ids_sent_alone_must_name_ready_sources(engine: Engine) -> None:
    """Checked as a chat checks them, before anything is stored."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        pending = _ready(session, workspace_id, "Scan", library)
        session.get(Document, pending).status = DocumentStatus.PENDING
        thread = _agent_thread(session, workspace_id)

        with pytest.raises(HTTPException) as refused:
            turn_sources(
                session, thread, MessageCreate(text="hi", document_ids=[pending])
            )

        assert refused.value.status_code == 409
        assert thread.source_scope is None


def test_the_note_names_no_file_and_says_earlier_passages_no_longer_apply(
    engine: Engine,
) -> None:
    """The thread's folder holds only its sources; what was read before the untick does not count."""
    with create_session_factory(engine)() as session:
        workspace_id, library = _workspace_with_library(session)
        ticked = _ready(session, workspace_id, "Plan", library)
        thread = _agent_thread(session, workspace_id)

        sources = turn_sources(
            session,
            thread,
            MessageCreate(text="hi", source_scope=SourceScope(document_ids=[ticked])),
        )

        assert sources.note == (
            f"[surfsense-scope: {ticked}]\n"
            "The user chose 1 source for this chat; it is the file in sources/. "
            "Use only that one. Passages read earlier from other sources no longer apply."
        )
        assert "Plan" not in sources.note
