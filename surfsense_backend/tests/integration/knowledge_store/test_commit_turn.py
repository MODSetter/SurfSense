"""End-of-turn commit body: working-copy diff → one revision → receipts.

Real git engine + real Redis write lock; only the LLM boundary is faked.
"""

from __future__ import annotations

import contextlib

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import select

import app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_turn as commit_turn
from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_turn import (
    commit_turn_working_copy,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.git_tree import (
    GitTreeBackend,
)
from app.config import config as app_config
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.locks import workspace_write_lock

pytestmark = pytest.mark.integration

THREAD_ID = 42
USER_ID = "1"


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def llm() -> FakeListChatModel:
    return FakeListChatModel(responses=["docs: capture turn output"])


async def _turn_writes(workspace_id, files: dict[str, bytes]) -> KnowledgeStore:
    """Simulate a turn: materialize the thread's working copy and write into it."""
    store = KnowledgeStore.for_workspace(workspace_id)
    copy = await store.open_working_copy(f"thread-{THREAD_ID}")
    for rel, content in files.items():
        target = copy.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return store


async def _commit(workspace_id, llm):
    return await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )


async def _committed_turn(workspace_id, llm, files: dict[str, bytes]) -> KnowledgeStore:
    """Leave the store one revision in, so the next turn can edit or drop files."""
    store = await _turn_writes(workspace_id, files)
    await _commit(workspace_id, llm)
    return store


async def _next_turn_copy(store: KnowledgeStore):
    """A fresh copy for the following turn, materialized from the committed tree."""
    return await store.open_working_copy(f"thread-{THREAD_ID}")


def _operations(delta) -> dict[str, str]:
    return {r["preview"]: r["operation"] for r in delta["receipts"]}


def _yielding(session):
    """Point the commit body's own session at the test transaction."""

    @contextlib.asynccontextmanager
    async def _session():
        yield session

    return _session


class _Runtime:
    """Enough of ``ToolRuntime`` for the backend to resolve a working copy."""

    def __init__(self, thread_id: str) -> None:
        self.config = {"configurable": {"thread_id": thread_id}}
        self.state: dict = {}
        self.tool_call_id = "call_x"


async def test_commits_the_turns_net_changes_as_one_revision(
    knowledge_root, workspace_id, llm
):
    store = await _turn_writes(workspace_id, {"documents/note.md": b"hello"})

    delta = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    revisions = await store.list_revisions()
    assert len(revisions) == 1
    assert await store.read_as_of(revisions[0].id, "documents/note.md") == b"hello"

    receipts = delta["receipts"]
    assert [r["status"] for r in receipts] == ["success"]
    assert receipts[0]["external_id"] == revisions[0].id
    assert receipts[0]["operation"] == "write_file"


async def test_message_carries_subject_and_thread_trailer(
    knowledge_root, workspace_id, llm
):
    store = await _turn_writes(workspace_id, {"documents/note.md": b"hello"})

    await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    message = (await store.list_revisions())[0].message
    assert message.startswith("docs: capture turn output")
    assert f"Thread: {THREAD_ID}" in message


async def test_attributes_author_to_user_and_committer_to_agent(
    knowledge_root, workspace_id, llm
):
    store = await _turn_writes(workspace_id, {"documents/note.md": b"hello"})

    await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    rev = (await store.list_revisions())[0]
    assert USER_ID in rev.author
    assert rev.author != rev.committer
    assert "agent" in rev.committer.lower()


async def test_discards_the_copy_so_a_second_commit_is_a_no_op(
    knowledge_root, workspace_id, llm
):
    await _turn_writes(workspace_id, {"documents/note.md": b"hello"})

    first = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )
    second = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    assert first is not None
    assert second is None


async def test_a_turn_that_never_touched_the_store_commits_nothing(
    knowledge_root, workspace_id, llm
):
    delta = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    assert delta is None
    store = KnowledgeStore.for_workspace(workspace_id)
    assert await store.get_current_revision() is None


async def test_an_untouched_copy_records_nothing(knowledge_root, workspace_id, llm):
    store = await _turn_writes(workspace_id, {})

    delta = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )

    assert delta is None
    assert await store.get_current_revision() is None


async def test_lock_contention_yields_failed_receipts_and_keeps_the_copy(
    knowledge_root, workspace_id, llm, short_lock_wait
):
    store = await _turn_writes(workspace_id, {"documents/note.md": b"hello"})

    async with workspace_write_lock(workspace_id):
        delta = await commit_turn_working_copy(
            workspace_id=workspace_id,
            thread_id=THREAD_ID,
            created_by_id=USER_ID,
            llm=llm,
        )

    assert [r["status"] for r in delta["receipts"]] == ["failed"]
    assert await store.get_current_revision() is None
    # The copy survives, so the thread's next turn commits the leftover work.
    retry = await commit_turn_working_copy(
        workspace_id=workspace_id,
        thread_id=THREAD_ID,
        created_by_id=USER_ID,
        llm=llm,
    )
    assert [r["status"] for r in retry["receipts"]] == ["success"]


# --- Every kind of change a turn can make ---
#
# Receipts are the orchestrator's ground truth for what the agent did, so the
# operation each kind maps to has to be pinned per kind — a turn that only ever
# adds files leaves the modification and removal mappings unverified.


async def test_an_edited_file_is_recorded_as_a_modification(
    knowledge_root, workspace_id, llm
):
    store = await _committed_turn(workspace_id, llm, {"documents/note.md": b"hello"})

    copy = await _next_turn_copy(store)
    (copy.path / "documents/note.md").write_bytes(b"hello again")
    delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {"documents/note.md": "edit_file"}
    revision = (await store.list_revisions())[0].id
    assert await store.read_as_of(revision, "documents/note.md") == b"hello again"


async def test_a_deleted_file_is_recorded_as_a_removal(
    knowledge_root, workspace_id, llm
):
    store = await _committed_turn(workspace_id, llm, {"documents/note.md": b"hello"})

    copy = await _next_turn_copy(store)
    (copy.path / "documents/note.md").unlink()
    delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {"documents/note.md": "rm"}
    revision = (await store.list_revisions())[0].id
    assert await store.list_paths(revision) == []


async def test_a_moved_file_is_recorded_as_one_move(knowledge_root, workspace_id, llm):
    """A move is committed as a removal plus a write, but read back as a rename:
    git recognises the content, which is what lets the index move the document's
    row instead of replacing it. The receipt reports the move it was."""
    store = await _committed_turn(workspace_id, llm, {"documents/old.md": b"hello"})

    copy = await _next_turn_copy(store)
    (copy.path / "documents/old.md").rename(copy.path / "documents/new.md")
    delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {"documents/new.md": "move_file"}
    revision = (await store.list_revisions())[0].id
    assert [e.path for e in await store.list_paths(revision)] == ["documents/new.md"]


async def test_a_mixed_turn_records_one_receipt_per_change(
    knowledge_root, workspace_id, llm
):
    store = await _committed_turn(
        workspace_id, llm, {"documents/kept.md": b"a", "documents/dropped.md": b"b"}
    )

    copy = await _next_turn_copy(store)
    (copy.path / "documents/kept.md").write_bytes(b"a edited")
    (copy.path / "documents/dropped.md").unlink()
    (copy.path / "documents/added.md").write_bytes(b"c")
    delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {
        "documents/kept.md": "edit_file",
        "documents/dropped.md": "rm",
        "documents/added.md": "write_file",
    }
    assert len(await store.list_revisions()) == 2


async def test_a_delegated_write_is_committed_by_the_parent_turn(
    knowledge_root, workspace_id, llm
):
    """A subagent's write must reach the turn's revision, not vanish.

    Writes through the backend rather than a hand-built copy id: the defect was
    the backend and the commit deriving that id differently.
    """
    backend = GitTreeBackend(workspace_id, _Runtime(f"{THREAD_ID}::task:call_x"))
    await backend.awrite("/documents/delegated.md", "from the subagent")

    delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {"documents/delegated.md": "write_file"}
    store = KnowledgeStore.for_workspace(workspace_id)
    revision = (await store.list_revisions())[0].id
    assert (
        await store.read_as_of(revision, "documents/delegated.md")
        == b"from the subagent"
    )
    # The copy is discarded, not left behind as an orphan.
    assert not (
        knowledge_root / ".working_copies" / str(workspace_id) / f"thread-{THREAD_ID}"
    ).exists()


async def test_the_turn_announces_the_rows_it_just_created(
    knowledge_root, db_session, db_workspace, llm, monkeypatch
):
    """The sidebar shows a new note now, instead of when the embeddings land.

    Uses a real workspace row because the announcement carries a document id,
    and that id only exists once the projection has written the row.
    """
    monkeypatch.setattr("app.db.shielded_async_session", _yielding(db_session))
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        commit_turn,
        "dispatch_custom_event",
        lambda name, payload: events.append((name, payload)),
    )
    await _turn_writes(db_workspace.id, {"documents/note.xml": b"# Note\n\nbody\n"})

    await _commit(db_workspace.id, llm)

    assert [name for name, _ in events] == ["document_created"]
    payload = events[0][1]
    assert payload["title"] == "note"
    assert payload["virtualPath"] == "/documents/note.xml"
    row = (
        await db_session.execute(
            select(Document).where(Document.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert payload["id"] == row.id


async def test_failed_receipts_cover_removals_too(
    knowledge_root, workspace_id, llm, short_lock_wait
):
    store = await _committed_turn(workspace_id, llm, {"documents/note.md": b"hello"})

    copy = await _next_turn_copy(store)
    (copy.path / "documents/note.md").unlink()
    async with workspace_write_lock(workspace_id):
        delta = await _commit(workspace_id, llm)

    assert _operations(delta) == {"documents/note.md": "rm"}
    assert [r["status"] for r in delta["receipts"]] == ["failed"]
