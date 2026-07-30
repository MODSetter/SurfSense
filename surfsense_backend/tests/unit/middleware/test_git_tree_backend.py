"""GitTreeBackend: ``/documents`` ops land on the turn's private working copy."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.git_tree import (
    GitTreeBackend,
    thread_working_copy_id,
)
from app.config import config as app_config
from app.knowledge_store.engines.git import GitContentEngine

pytestmark = pytest.mark.unit

WORKSPACE_ID = 7
AUTHOR = "SurfSense <1@users.surfsense>"


class _RuntimeStub:
    def __init__(self, thread_id: str | None = "t1") -> None:
        configurable = {} if thread_id is None else {"thread_id": thread_id}
        self.config = {"configurable": configurable}
        self.state: dict = {}
        self.tool_call_id = "call-1"


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


def _engine(knowledge_root) -> GitContentEngine:
    return GitContentEngine(
        knowledge_root / str(WORKSPACE_ID),
        knowledge_root / ".working_copies" / str(WORKSPACE_ID),
    )


class TestTurnWorkingCopyId:
    def test_is_keyed_by_conversation_thread(self):
        assert thread_working_copy_id("abc") == "thread-abc"

    def test_falls_back_when_thread_id_is_missing(self):
        assert thread_working_copy_id(None) == "thread-adhoc"

    def test_a_subagent_resolves_its_parent_turns_copy(self):
        # Subagents run under a namespaced thread id. They are part of the
        # parent's turn, not turns of their own, so they must land in the copy
        # the end-of-turn commit reads — which is keyed by the parent thread.
        assert thread_working_copy_id("21::task:call_x") == "thread-21"

    def test_nested_subagents_resolve_the_same_copy(self):
        assert thread_working_copy_id("21::task:call_x::task:call_y") == "thread-21"


class TestGitTreeBackend:
    async def test_write_lands_on_the_turns_working_copy(self, knowledge_root):
        backend = GitTreeBackend(WORKSPACE_ID, _RuntimeStub())
        res = await backend.awrite("/documents/note.md", "hello")
        assert res.error is None

        # The mount targets the copy's documents/ subtree, so the repo path
        # keeps the prefix — the same path the recorder and seeder produce.
        copy_file = (
            knowledge_root
            / ".working_copies"
            / str(WORKSPACE_ID)
            / "thread-t1"
            / "documents"
            / "note.md"
        )
        assert copy_file.read_text() == "hello"

    async def test_tool_calls_share_one_copy_and_diff_reports_the_turn(
        self, knowledge_root
    ):
        # Each tool call constructs a fresh backend; the copy is shared via its id.
        await GitTreeBackend(WORKSPACE_ID, _RuntimeStub()).awrite(
            "/documents/note.md", "hello"
        )
        read_back = await GitTreeBackend(WORKSPACE_ID, _RuntimeStub()).aread(
            "/documents/note.md"
        )
        assert "hello" in read_back

        engine = _engine(knowledge_root)
        assert engine.diff_working_copy("thread-t1") == (
            {"documents/note.md": b"hello"},
            [],
        )

    async def test_committed_content_is_readable_and_deletable(self, knowledge_root):
        engine = _engine(knowledge_root)
        engine.record(
            writes={"documents/guides/setup.md": b"step one"},
            removes=[],
            message="seed",
            author=AUTHOR,
        )

        backend = GitTreeBackend(WORKSPACE_ID, _RuntimeStub())
        assert "step one" in await backend.aread("/documents/guides/setup.md")

        res = await backend.adelete_file("/documents/guides/setup.md")
        assert res.error is None
        assert engine.diff_working_copy("thread-t1") == (
            {},
            ["documents/guides/setup.md"],
        )

    async def test_mkdir_enables_writes_into_new_folders(self, knowledge_root):
        backend = GitTreeBackend(WORKSPACE_ID, _RuntimeStub())
        res = await backend.amkdir("/documents/research")
        assert res.error is None
        write = await backend.awrite("/documents/research/a.md", "x")
        assert write.error is None

    async def test_move_relocates_within_the_copy(self, knowledge_root):
        backend = GitTreeBackend(WORKSPACE_ID, _RuntimeStub())
        await backend.awrite("/documents/old.md", "content")
        res = await backend.amove("/documents/old.md", "/documents/new.md")
        assert res.error is None
        assert "content" in await backend.aread("/documents/new.md")

    async def test_paths_outside_documents_are_rejected(self, knowledge_root):
        backend = GitTreeBackend(WORKSPACE_ID, _RuntimeStub())
        result = await backend.aread("/elsewhere/x.md")
        assert result.startswith("Error:")

    async def test_a_subagents_write_is_visible_to_the_orchestrator(
        self, knowledge_root
    ):
        # The delegated write and the orchestrator's own view are one tree, so
        # the turn's single commit picks the subagent's work up.
        await GitTreeBackend(WORKSPACE_ID, _RuntimeStub("t1::task:call_x")).awrite(
            "/documents/delegated.md", "from the subagent"
        )

        orchestrator = GitTreeBackend(WORKSPACE_ID, _RuntimeStub("t1"))
        assert "from the subagent" in await orchestrator.aread("/documents/delegated.md")
        engine = _engine(knowledge_root)
        assert engine.diff_working_copy("thread-t1") == (
            {"documents/delegated.md": b"from the subagent"},
            [],
        )

    async def test_parallel_threads_get_isolated_copies(self, knowledge_root):
        await GitTreeBackend(WORKSPACE_ID, _RuntimeStub("t1")).awrite(
            "/documents/mine.md", "t1 data"
        )
        other = await GitTreeBackend(WORKSPACE_ID, _RuntimeStub("t2")).aread(
            "/documents/mine.md"
        )
        assert other.startswith("Error:")
