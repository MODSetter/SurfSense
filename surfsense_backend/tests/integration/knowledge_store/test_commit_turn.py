"""End-of-turn commit body: working-copy diff → one revision → receipts.

Real git engine + real Redis write lock; only the LLM boundary is faked.
"""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_turn import (
    commit_turn_working_copy,
)
from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.write_lock import workspace_write_lock

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
