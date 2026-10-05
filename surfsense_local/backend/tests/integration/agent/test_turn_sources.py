"""An agent turn's sources resolve as a chat's do, with no opencode needed."""

import pytest
from sqlalchemy import Engine

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
        assert sources.shown is not None and len(sources.shown["titles"]) == 1002
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
