"""What the end-of-stream safety net does to a turn that stopped for approval.

The net exists for the turn that dies mid-flight: it commits the working copy
the ``aafter_agent`` hook never reached. A turn paused at an approval gate looks
the same from here — the stream ends either way — but it is coming back, and the
copy is the only place its work so far exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.agent.event_loop import stream_agent_events
from app.tasks.chat.streaming.shared.stream_result import StreamResult

pytestmark = pytest.mark.integration

THREAD_ID = 4321
COPY_ID = f"thread-{THREAD_ID}"


@dataclass
class _Interrupt:
    value: dict[str, Any]


@dataclass
class _Task:
    interrupts: tuple[_Interrupt, ...] = ()


@dataclass
class _State:
    """Stand-in for the snapshot ``aget_state`` returns.

    Empty ``values`` keeps the legacy staged-state net a no-op, so the only
    write path under test is the git-native one.
    """

    tasks: list[_Task] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)


class _Agent:
    """Streams nothing; the turn's work is already on disk in the copy."""

    def __init__(self, state: _State) -> None:
        self._state = state
        self.updates: list[Any] = []

    async def astream_events(self, *_args, **_kwargs):
        return
        yield  # pragma: no cover - makes this an async generator

    async def aget_state(self, _config):
        return self._state

    async def aupdate_state(self, _config, delta, **_kwargs):
        self.updates.append(delta)


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def _run_turn(workspace_id: int, state: _State) -> _Agent:
    agent = _Agent(state)
    async for _ in stream_agent_events(
        agent,
        {"configurable": {"thread_id": str(THREAD_ID)}},
        {},
        VercelStreamingService(),
        StreamResult(),
        fallback_commit_workspace_id=workspace_id,
        fallback_commit_created_by_id="1",
        fallback_commit_filesystem_mode=FilesystemMode.CLOUD,
        fallback_commit_thread_id=THREAD_ID,
    ):
        pass
    return agent


async def _copy_with_pending_work(workspace_id: int) -> tuple[Any, Any]:
    """A copy holding one written file and one folder the agent just made."""
    store = KnowledgeStore.for_workspace(workspace_id)
    copy = await store.open_working_copy(COPY_ID)
    documents = copy.path / "documents"
    documents.mkdir(exist_ok=True)
    (documents / "draft.md").write_text("# Draft\n")
    (documents / "crud-test").mkdir(exist_ok=True)
    return store, copy


async def test_a_turn_paused_for_approval_keeps_its_working_copy(
    knowledge_root, db_workspace, workspace_flip
):
    """The folder is the part that cannot be rebuilt: git stores no empty
    directory, so discarding here loses it for good — and the write the approval
    was granted for then fails for want of its parent."""
    workspace_flip(True)
    _, copy = await _copy_with_pending_work(db_workspace.id)
    pending_approval = {
        "type": "approval",
        "message": "Approve writing draft.md?",
        "action": {"name": "write_file", "args": {"file_path": "/documents/draft.md"}},
        "context": {},
    }
    paused = _State(tasks=[_Task(interrupts=(_Interrupt(value=pending_approval),))])

    await _run_turn(db_workspace.id, paused)

    assert copy.path.exists()
    assert (copy.path / "documents" / "draft.md").read_text() == "# Draft\n"
    assert (copy.path / "documents" / "crud-test").is_dir()


async def test_a_finished_turn_still_gets_its_safety_net(
    knowledge_root, db_workspace, workspace_flip
):
    """The net's own reason for existing: no approval pending means the turn is
    over, and an uncommitted copy means the hook never ran."""
    workspace_flip(True)
    store, copy = await _copy_with_pending_work(db_workspace.id)

    agent = await _run_turn(db_workspace.id, _State())

    assert not copy.path.exists()
    revision = await store.get_current_revision()
    paths = {entry.path for entry in await store.list_paths(revision)}
    assert "documents/draft.md" in paths
    assert agent.updates, "the commit's delta should reach the graph"
